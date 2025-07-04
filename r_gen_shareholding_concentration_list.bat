:: 專門處理 阿信的 籌碼集中度選股 清單 (約150檔)
@echo off
python src\fetch\finmind_db_fetcher.py shareholding_concentration_list.txt

@echo off
python src\gen_filtered_report_db.py

