:: 專門處理 阿信的 籌碼集中度選股 清單 (約150檔)
@echo off
python src\fetch\finmind_db_fetcher.py shareholding_concentration_list.txt
:: 確保即將篩選的股票數據是最新的

@echo off
python src\gen_filtered_report_db.py
:: 針對RS>90的強勢股進行篩選，生成XQ匯入檔 
:: 預設是讀取 shareholding_concentration_list.txt，因為這個filter最初是為了 籌碼集中度選股 而設計的
