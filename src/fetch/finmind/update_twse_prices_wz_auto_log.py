import sys
from pathlib import Path
from datetime import datetime
import traceback

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

    # === 導入 src 模組路徑，解決 relative import 問題 ===
    sys.path.append(str(Path(__file__).resolve().parents[2]))

    from fetch.finmind.finmind_db_fetcher import fetch_with_finmind_recent
    from fetch.finmind.fetch_wearn_price_all_stocks_52weeks_threaded_safe import get_all_stock_ids
    from FinMind.data import DataLoader
    import sqlite3
    import os
    import time

    account_index = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    safe_print(f"🧾 使用帳號序號: {account_index}")

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        safe_print(f"❌ 找不到 .env 檔案: {env_path}")
        raise SystemExit()

    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)

    user = os.getenv(f"FINMIND_USER_{account_index}")
    password = os.getenv(f"FINMIND_PASSWORD_{account_index}")
    if not user or not password:
        safe_print(f"❌ 找不到第 {account_index} 組帳號的 .env 設定")
        raise SystemExit()

    safe_print("🔐 開始登入 FinMind ...")
    dl = DataLoader()
    success = dl.login(user_id=user, password=password)
    if not success:
        safe_print(f"❌ 登入失敗: {success}")
        raise SystemExit()

    safe_print("✅ 登入成功，開始更新資料...")
    fetch_with_finmind_recent("^TWII", dl, months=3)
    safe_print("🎉 補資料完成")

except Exception as e:
    safe_print(f"❌ 發生例外: {e}")
    safe_print(traceback.format_exc())

finally:
    try:
        log_fp.close()
    except:
        pass
