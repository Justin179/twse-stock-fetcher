:: 專門處理 阿信的 收盤價大於上個月高點 清單 (約300檔)

@echo off
REM %~1 代表外部傳進來的乖離率
python src\gen_filtered_report_db.py break_above_last_months_high.txt %~1
:: 針對RS>90的強勢股進行篩選，生成XQ匯入檔 
:: 預設是讀取 shareholding_concentration_list.txt，因為這個filter最初是為了 籌碼集中度選股 而設計的
