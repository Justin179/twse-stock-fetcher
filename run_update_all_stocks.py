import subprocess
import sys
from pathlib import Path

# 設定 virtualenv Python 路徑
python_path = Path("venv/Scripts/python.exe")

# 路徑轉絕對（避免排程中路徑錯誤）
base_dir = Path(__file__).resolve().parent
py1 = base_dir / "src" / "fetch" / "fubon" / "fetch_fubon_daily_ohlcv_all_stocks_to_db_fixed.py"
py2 = base_dir / "src" / "fetch" / "finmind" / "update_twse_prices_wz_param.py"

print("[1/2] 📥 開始執行 Fubon OHLCV 更新...")
subprocess.run([str(python_path), "-m", "src.fetch.fubon.fetch_fubon_daily_ohlcv_all_stocks_to_db_fixed"], check=True)
print("✅ Fubon OHLCV 更新完成")

print("[2/2] 📥 開始執行 TWSE Prices 補資料...")
subprocess.run([str(python_path), "-m", "src.fetch.finmind.update_twse_prices_wz_param", "1"], check=True)
print("✅ TWSE Prices 補資料完成")
