:: 專門處理 RS>90的強勢股 清單
@echo off
python src\fetch\finmind_db_fetcher.py high_relative_strength_stocks.txt

@echo off
python src\gen_filtered_report_db.py high_relative_strength_stocks.txt

