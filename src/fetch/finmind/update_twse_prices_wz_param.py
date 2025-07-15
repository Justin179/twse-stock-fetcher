import time
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from FinMind.data import DataLoader
from finmind_db_fetcher import fetch_with_finmind_recent
from fetch_wearn_price_all_stocks_52weeks_threaded_safe import get_all_stock_ids
from dotenv import load_dotenv
import os
import logging

# 支援 透過傳入數字 切帳號 (1, 2, 3 ...)
# 例如：python update_twse_prices_with_param_login.py 1
'''
用台積電（2330）的歷史資料取得最新一筆交易日期。
查資料庫 twse_prices，比對是否已有最新交易日的資料。已經有最新的ohlcv資料，就不發出請求(省著用)
到finmind抓過去13個月的資料，insert or ignore到 twse_prices 資料庫。

特殊邏輯: 1輪抓480檔個股，只有在回血到request ≥ 510 為綠燈放行 (變綠燈前，每10分鐘查看一次變綠燈了沒有)

主要用途: (手動)補資料
帳號1 + justin_uob: 480筆
帳號2 + 手機: 480筆
帳號3 + 手機(開關飛航，利用浮動ip): 480筆
理論上1次可以更到 1440筆資料 (反正先這樣用用看，不行再調整)
'''

logging.getLogger("FinMind").setLevel(logging.WARNING)

DB_PATH = "data/institution.db"
WAIT_SECONDS = 600  # 每次等待 10 分鐘
MIN_AVAILABLE = 510  # ✅ 修正：只有當可用 request ≥ 510 才放行
MAX_USE_PER_ROUND = 480  # ✅ 修正：每輪最多只使用 480 request

log_fp = None  # ✅ 用於 log 紀錄

def safe_print(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted = f"{timestamp} | {msg}"
    print(formatted)
    if log_fp:
        log_fp.write(formatted + "\n")

def refresh_quota(dl: DataLoader):
    try:
        _ = dl.taiwan_stock_info()
    except:
        pass

def wait_for_quota(dl: DataLoader):
    while True:
        refresh_quota(dl)
        available = dl.api_usage_limit - dl.api_usage
        safe_print(f"📊 FinMind 可用 request 數：{available}")
        if available >= MIN_AVAILABLE:
            return
        safe_print(f"⏳ request 不足，等待 {WAIT_SECONDS} 秒再重試...")
        time.sleep(WAIT_SECONDS)

# ✅ 新增：取得台積電的最新交易日，作為本次更新的基準日
def get_latest_trading_date(dl: DataLoader) -> str:
    try:
        df = dl.taiwan_stock_daily(
            stock_id="2330",
            start_date=(datetime.today() - timedelta(days=31)).strftime("%Y-%m-%d"), 
            end_date=datetime.today().strftime("%Y-%m-%d")
        )

        if df.empty:
            raise ValueError("2330 無資料")

        latest_date = df["date"].max()
        safe_print(f"📅 最新交易日（從 2330 抓）: {latest_date}")
        return latest_date

    except Exception as e:
        safe_print(f"❌ 抓取最新交易日失敗：{e}")
        return None

# ✅ 新增：過濾掉 twse_prices 資料庫中已經是最新交易日的個股
def filter_already_updated(all_ids: list[str], latest_date: str) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in all_ids)
    cursor.execute(
        f"""
        SELECT stock_id, MAX(date) as max_date
        FROM twse_prices
        WHERE stock_id IN ({placeholders})
        GROUP BY stock_id
        """, all_ids
    )
    rows = cursor.fetchall() # 獲取每個個股的最新日期 from twse_prices
    conn.close()

    latest_map = {sid: date for sid, date in rows} # 只是轉換成字典(stock_id: latest_date)
    filtered = [sid for sid in all_ids if latest_map.get(sid) != latest_date] # 只保留那些最新日期不是我們抓取的最新交易日的個股
    safe_print(f"🔍 篩選後剩下 {len(filtered)} 檔個股需要更新")
    return filtered

def main():
    # ✅ 讀取帳號索引參數，預設為 1
    if len(sys.argv) < 2:
        print("⚠️ 未提供帳號索引參數，預設使用帳號 1")
        account_index = 1
    else:
        try:
            account_index = int(sys.argv[1])
        except:
            print("❌ 傳入的帳號索引參數無效，請使用 1, 2, 3 ...")
            return

    env_key = lambda key: os.getenv(f"{key}_{account_index}")
    user = env_key("FINMIND_USER")
    password = env_key("FINMIND_PASSWORD")
    token = env_key("FINMIND_TOKEN")

    if not user or not password:
        print(f"❌ 找不到第 {account_index} 組帳號的 .env 設定")
        return

    dl = DataLoader()
    success = dl.login(user_id=user, password=password)
    if not success:
        print("❌ 登入失敗")
        return
    if token:
        dl.token = token

    safe_print(f"🔑 使用帳號 {account_index}: {user}")

    global log_fp

    # ✅ 僅在排程執行（非互動模式）且星期天時跳過
    # if not sys.stdin.isatty() and datetime.today().weekday() == 6:
    #     print("📅 今天是星期天，排程執行中，略過更新")
    #     return

    Path("logs").mkdir(exist_ok=True)
    log_filename = Path("logs") / f"twse_prices_update_{datetime.today().strftime('%Y%m%d_%H%M%S')}.log"
    log_fp = open(log_filename, "w", encoding="utf-8")

    all_ids = get_all_stock_ids()

    # ✅ 加入：取得最新交易日，並過濾已更新個股
    latest_date = get_latest_trading_date(dl)
    safe_print(f"📅 最新交易日: {latest_date}")

    if not latest_date:
        print("❌ 無法取得最新交易日，終止執行")
        return
    all_ids = filter_already_updated(all_ids, latest_date)

    pending = all_ids.copy()
    total = len(pending)
    safe_print(f"🚀 開始更新 twse_prices（共 {total} 檔個股）")

    round_count = 0
    while pending: # 繼續處理直到沒有待處理的個股
        wait_for_quota(dl) # 等待回血到 510個可用requests 才能繼續
        round_count += 1
        safe_print(f"🔄 第 {round_count} 輪開始")

        use_now = min(len(pending), MAX_USE_PER_ROUND) # 這一輪（round）要處理的股票數量 (從 pending 清單中抓出幾檔個股來發送 request, 最多480檔)
        current_batch = pending[:use_now] # 取出這一輪要處理的股票代碼。
        pending = pending[use_now:] # 更新 pending 清單，移除已處理的股票代碼。

        done, skipped = 0, 0
        skipped_ids = []  # ✅ 新增：記錄被 skip 的個股代碼

        for stock_id in current_batch:
            for attempt in range(1, 3):  # ✅ 最多嘗試兩次
                result = fetch_with_finmind_recent(stock_id, dl, months=13) # 52週(insert or ignore)
                # result = fetch_with_finmind_data_full_wash(stock_id, dl, months=69) # 整個洗一次(update)

                if result is None:
                    done += 1
                    break  # 成功就跳出 retry 迴圈
                elif attempt == 2:
                    skipped += 1
                    skipped_ids.append(stock_id)

        safe_print(f"✅ 本輪完成 {done} 檔，略過 {skipped} 檔，剩餘 {len(pending)} 檔")

        if skipped_ids:
            safe_print(f"⚠️ 被跳過的股票代碼（共 {len(skipped_ids)} 檔）: {', '.join(skipped_ids)}")

    safe_print("🎉 全部更新完成")
    if log_fp:
        log_fp.write("🎉 全部更新完成\n")
        log_fp.close()

if __name__ == "__main__":
    main()
