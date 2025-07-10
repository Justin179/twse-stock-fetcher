:: 專門處理 隱者App的策略選股: 贏勢+價值+動能+口袋+自訂贏勢
@REM @echo off
@REM python src\fetch\finmind_db_fetcher.py hermit_watchlist.txt
:: 確保即將篩選的股票數據是最新的

@echo off
python src\gen_filtered_report_db.py hermit_watchlist.txt
:: 針對隱者App的策略選股，生成XQ匯入檔 
