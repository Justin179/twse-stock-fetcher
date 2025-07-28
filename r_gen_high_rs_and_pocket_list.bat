:: 專門處理 RS>90的強勢股 清單 (約250檔)
@echo off
python src\analyze\filter_strong_stocks_by_rs_rsi.py
:: 從db找出RS>90的強勢股，並把結果存到 high_relative_strength_stocks.txt (append after「# 找出RS>90的強勢股」)

@echo off
python src\tools\append_my_stock_holdings.py
:: 把我的持股清單也加入到強勢股清單中(my_stock_holdings.txt 加到 high_relative_strength_stocks.txt)


@echo off
python src\gen_filtered_report_db.py high_relative_strength_stocks.txt
:: 針對RS>90的強勢股進行篩選(隱者清單 & 持股清單已經融入)，生成XQ匯入檔

