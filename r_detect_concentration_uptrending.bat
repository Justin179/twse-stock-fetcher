
@echo off
REM %~1 代表外部傳進來的乖離率
python src\analyze\detect_break_high_low_signals.py my_stock_holdings.txt %~1
:: 用來看看「我的庫存清單」中有突破或跌破訊號的股票，找出本週或本月的強勢股或弱勢股
:: 由於呼叫富邦api(單線程同步)，會花比較久才回應，不適合跑high_relative_strength_stocks.txt 因為太多檔了
:: 已經把隱者清單混入到預設的my_stock_holdings.txt中，所以不需要再額外處理隱者清單

