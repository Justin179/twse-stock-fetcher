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
WAIT_SECONDS = 300  # 每次等待 5 分鐘
MIN_AVAILABLE = 500  # ✅ 修正：只有當可用 request ≥ 500 才放行
MAX_USE_PER_ROUND = 450  # ✅ 修正：每輪最多只使用 450 request

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

def main():
    load_dotenv()
    dl = DataLoader()
    success = dl.login(user_id=os.getenv("FINMIND_USER"), password=os.getenv("FINMIND_PASSWORD"))
    if not success:
        print("❌ 登入失敗")
        return

    Path("logs").mkdir(exist_ok=True)
    all_ids = get_all_stock_ids()
    pending = all_ids.copy()
    total = len(pending)
    safe_print(f"🚀 開始更新 twse_prices（共 {total} 檔個股）")

    round_count = 0
    while pending: # 繼續處理直到沒有待處理的個股
        wait_for_quota(dl) #（可用 request 數 < 400），就會休息一段時間（預設 5 分鐘）再重試
        round_count += 1
        safe_print(f"🔄 第 {round_count} 輪開始")

        use_now = min(len(pending), MAX_USE_PER_ROUND) # 這一輪（round）要處理的股票數量 (從 pending 清單中抓出幾檔個股來發送 request, 最多500 檔)
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