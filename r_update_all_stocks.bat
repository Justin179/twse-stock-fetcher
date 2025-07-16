@echo off
cd /d %~dp0
echo [1/2] 🚀 開始執行 Fubon OHLCV 更新...
python src\fetch\fubon\fetch_fubon_daily_ohlcv_all_stocks_to_db_fixed.py
echo [1/2] ✅ Fubon OHLCV 更新完成

echo [2/2] 🚀 開始執行 TWSE Prices 補資料...
python src\fetch\finmind\update_twse_prices_wz_param.py 1
echo [2/2] ✅ TWSE Prices 補資料完成

pause
