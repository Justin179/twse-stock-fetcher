import time
import sqlite3
from datetime import datetime
from pathlib import Path
from FinMind.data import DataLoader
from finmind_db_fetcher import fetch_with_finmind_recent, get_existing_dates
from fetch_wearn_price_all_stocks_52weeks_threaded_safe import get_all_stock_ids
from dotenv import load_dotenv
import os

DB_PATH = "data/institution.db"
WAIT_SECONDS = 600  # 每次等待 10 分鐘
MIN_AVAILABLE = 510  # ✅ 修正：只有當可用 request ≥ 510 才放行
MAX_USE_PER_ROUND = 480  # ✅ 修正：每輪最多只使用 480 request

def safe_print(msg):
    print(f"{datetime.now().strftime('%H:%M:%S')} | {msg}")

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
            start_date="2024-01-01",  # 任意合理時間即可
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
    load_dotenv()
    dl = DataLoader()
    success = dl.login(user_id=os.getenv("FINMIND_USER"), password=os.getenv("FINMIND_PASSWORD"))
    if not success:
        print("❌ 登入失敗")
        return

    Path("logs").mkdir(exist_ok=True)
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
        for stock_id in current_batch:
            result = fetch_with_finmind_recent(stock_id, dl, months=13)
            if result is None:
                done += 1
            else:
                skipped += 1
        safe_print(f"✅ 本輪完成 {done} 檔，略過 {skipped} 檔，剩餘 {len(pending)} 檔")

    safe_print("🎉 全部更新完成")

if __name__ == "__main__":
    main()
