from pathlib import Path
from datetime import datetime, timedelta
import traceback
import sqlite3
import sys
import os
import time
from dotenv import load_dotenv
from FinMind.data import DataLoader

# === 提早建立 log ===
LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_path = LOG_DIR / f"twse_update_debug_{datetime.now():%Y%m%d_%H%M%S}.log"
log_fp = open(log_path, "w", encoding="utf-8")

def safe_print(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    line = f"{timestamp} | {msg}"
    print(line)
    try:
        log_fp.write(line + "\n")
        log_fp.flush()
    except:
        pass

try:
    safe_print(f"[{datetime.now()}] 🚀 開始執行 TWSE 補資料更新")
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from fetch.finmind.finmind_db_fetcher import fetch_with_finmind_recent
    from fetch.finmind.fetch_wearn_price_all_stocks_52weeks_threaded_safe import get_all_stock_ids

    # === 初始化帳號登入資訊 ===
    account_index = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    safe_print(f"🧾 使用帳號序號: {account_index}")

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        safe_print(f"❌ 找不到 .env 檔案: {env_path}")
        raise SystemExit()

    load_dotenv(dotenv_path=env_path)
    user = os.getenv(f"FINMIND_USER_{account_index}")
    password = os.getenv(f"FINMIND_PASSWORD_{account_index}")
    token = os.getenv(f"FINMIND_TOKEN_{account_index}")
    if not user or not password:
        safe_print(f"❌ 找不到第 {account_index} 組帳號的 .env 設定")
        raise SystemExit()

    # === 登入 FinMind ===
    safe_print("🔐 開始登入 FinMind ...")
    dl = DataLoader()
    success = dl.login(user_id=user, password=password)
    if not success:
        safe_print("❌ 登入失敗")
        raise SystemExit()
    if token:
        dl.token = token
    safe_print(f"✅ 登入成功: {user}")

    # === Constants ===
    DB_PATH = "data/institution.db"
    WAIT_SECONDS = 600
    MIN_AVAILABLE = 510
    MAX_USE_PER_ROUND = 480

    def refresh_quota(dl):
        try:
            _ = dl.taiwan_stock_info()
        except:
            pass

    def wait_for_quota(dl):
        while True:
            refresh_quota(dl)
            available = dl.api_usage_limit - dl.api_usage
            safe_print(f"📊 FinMind 可用 request 數：{available}")
            if available >= MIN_AVAILABLE:
                return
            safe_print(f"⏳ request 不足，等待 {WAIT_SECONDS} 秒再重試...")
            time.sleep(WAIT_SECONDS)

    def get_latest_trading_date(dl) -> str:
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

    def filter_already_updated(all_ids, latest_date):
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
        rows = cursor.fetchall()
        conn.close()
        latest_map = {sid: date for sid, date in rows}
        filtered = [sid for sid in all_ids if latest_map.get(sid) != latest_date]
        safe_print(f"🔍 篩選後剩下 {len(filtered)} 檔個股需要更新")
        return filtered

    # === 主流程開始 ===
    all_ids = get_all_stock_ids()
    latest_date = get_latest_trading_date(dl)
    if not latest_date:
        safe_print("❌ 無法取得最新交易日，終止執行")
        raise SystemExit()
    all_ids = filter_already_updated(all_ids, latest_date)

    pending = all_ids.copy()
    total = len(pending)
    safe_print(f"🚀 開始更新 twse_prices（共 {total} 檔個股）")

    round_count, done, skipped = 0, 0, 0
    while pending:
        wait_for_quota(dl)
        round_count += 1
        safe_print(f"🔄 第 {round_count} 輪開始")
        use_now = min(len(pending), MAX_USE_PER_ROUND)
        current_batch = pending[:use_now]
        pending = pending[use_now:]
        skipped_ids = []

        for stock_id in current_batch:
            for attempt in range(1, 3):
                result = fetch_with_finmind_recent(stock_id, dl, months=13)
                if result is None:
                    done += 1
                    break
                elif attempt == 2:
                    skipped += 1
                    skipped_ids.append(stock_id)

        safe_print(f"✅ 本輪完成 {done} 檔，略過 {skipped} 檔，剩餘 {len(pending)} 檔")
        if skipped_ids:
            safe_print(f"⚠️ 被跳過的股票代碼（共 {len(skipped_ids)} 檔）: {', '.join(skipped_ids)}")

    safe_print("🎉 全部更新完成")

except Exception as e:
    safe_print(f"❌ 發生例外: {e}")
    safe_print(traceback.format_exc())

finally:
    try:
        log_fp.close()
    except:
        pass
