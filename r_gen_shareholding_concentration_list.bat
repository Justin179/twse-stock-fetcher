:: 專門處理 阿信的 籌碼集中度選股 清單 (約150檔)

@echo off
REM %~1 代表外部傳進來的乖離率
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" (
	"%VENV_PYTHON%" "%SCRIPT_DIR%src\gen_filtered_report_db.py" %~1
) else (
	python "%SCRIPT_DIR%src\gen_filtered_report_db.py" %~1
)
:: 針對RS>90的強勢股進行篩選，生成XQ匯入檔 
:: 預設是讀取 shareholding_concentration_list.txt，因為這個filter最初是為了 籌碼集中度選股 而設計的
