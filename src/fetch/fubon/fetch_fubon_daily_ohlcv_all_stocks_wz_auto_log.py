from pathlib import Path
from datetime import datetime
import sys
import traceback

# === 設定 log 自動建立 ===
Path("logs").mkdir(exist_ok=True)
now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = Path(f"logs/fubon_ohlcv_update_{now_str}.log")

with open(log_path, "w", encoding="utf-8") as log_fp:
    def log(msg):
        print(msg)
        log_fp.write(msg + "\n")
        log_fp.flush()

    try:
        log(f"[{datetime.now()}] 🚀 開始執行 Fubon OHLCV 更新")

        # 將 src 加入模組搜尋路徑
        sys.path.append(str(Path(__file__).resolve().parents[2]))

        from common.login_helper import get_logged_in_sdk
        from fetch.finmind.fetch_wearn_price_all_stocks_52weeks_threaded_safe import get_all_stock_ids
        import sqlite3
        import time
        import pandas as pd

        DB_PATH = "data/institution.db"

        def safe_print(msg):
            timestamp = datetime.now().strftime('%H:%M:%S')
            line = f"{timestamp} | {msg}"
            print(line)
            log_fp.write(line + "\n")

        def fetch_daily_ohlcv(sdk, symbol, days=10):
            end = datetime.today()
            start = end - pd.Timedelta(days=days * 2)
            sdk.init_realtime()
            reststock = sdk.marketdata.rest_client.stock
            try:
                result = reststock.historical.candles(
                    symbol=symbol,
                    from_=start.strftime("%Y-%m-%d"),
                    to=end.strftime("%Y-%m-%d"),
                    timeframe="D"
                )
                return pd.DataFrame(result.get("data", []))
            except Exception as e:
                safe_print(f"{symbol} 抓取失敗: {e}")
                return None

        def get_latest_trading_date(sdk):
            df = fetch_daily_ohlcv(sdk, symbol="2330", days=10)
            if df is None or df.empty:
                safe_print("❌ 無法取得最新交易日")
                return None
            latest_date = pd.to_datetime(df["date"]).max().strftime("%Y-%m-%d")
            safe_print(f"📅 最新交易日: {latest_date}")
            return latest_date

        def filter_already_updated(all_ids, latest_date):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in all_ids)
            cursor.execute(
                f"SELECT stock_id, MAX(date) as max_date FROM twse_prices WHERE stock_id IN ({placeholders}) GROUP BY stock_id",
                all_ids
            )
            rows = cursor.fetchall()
            conn.close()
            latest_map = {sid: date for sid, date in rows}
            return [sid for sid in all_ids if latest_map.get(sid) != latest_date]

        def insert_ohlcv_to_db(stock_id, df):
            if df is None or df.empty:
                return 0
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            count = 0
            for _, row in df.iterrows():
                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO twse_prices (stock_id, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (stock_id, row["date"], row["open"], row["high"], row["low"], row["close"], row["volume"])
                    )
                    if cursor.rowcount > 0:
                        count += 1
                except Exception as e:
                    safe_print(f"{stock_id} 寫入資料庫失敗: {e}")
            conn.commit()
            conn.close()
            return count

        sdk = get_logged_in_sdk()
        all_ids = get_all_stock_ids()
        latest_date = get_latest_trading_date(sdk)
        if not latest_date:
            raise Exception("無法取得最新交易日")

        all_ids = filter_already_updated(all_ids, latest_date)
        safe_print(f"📝 需更新個股數: {len(all_ids)}")

        for idx, stock_id in enumerate(all_ids):
            for attempt in range(2):
                df = fetch_daily_ohlcv(sdk, symbol=stock_id, days=10)
                inserted = insert_ohlcv_to_db(stock_id, df)
                if inserted > 0 or attempt == 1:
                    break
            safe_print(f"✅ {stock_id} 完成寫入 {inserted} 筆")
            time.sleep(1.2)

        safe_print("🎉 全部更新完成")

    except Exception as e:
        log(f"[{datetime.now()}] ❌ 發生錯誤: {e}")
        log(traceback.format_exc())
