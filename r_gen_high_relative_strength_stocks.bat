:: 專門處理 RS>90的強勢股 清單 (約250檔)

:: 從db找出RS>90的強勢股，並把結果存到 high_relative_strength_stocks.txt
@echo off
python src\analyze\filter_strong_stocks_by_rs_rsi.py

@echo off
python src\fetch\finmind_db_fetcher.py high_relative_strength_stocks.txt

@echo off
python src\gen_filtered_report_db.py high_relative_strength_stocks.txt

