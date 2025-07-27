def append_unique_stocks(temp_path="temp_list.txt", holdings_path="my_stock_holdings.txt") -> str:
    """
    將 temp_path 中的股票代碼，去除重複後加入 holdings_path。
    如果已存在於 holdings_path 中，則不重複加入。

    Returns:
        str: 執行結果訊息
    """
    with open(temp_path, "r", encoding="utf-8") as f:
        temp_stocks = set(line.strip() for line in f if line.strip() and not line.startswith("#"))

    with open(holdings_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        current_holdings = set(line.strip() for line in lines if line.strip() and not line.startswith("#"))

    new_stocks = sorted(temp_stocks - current_holdings)

    if new_stocks:
        # 確保最後一行後有換行符號
        if lines and not lines[-1].endswith("\n"):
            with open(holdings_path, "a", encoding="utf-8") as f:
                f.write("\n")

        with open(holdings_path, "a", encoding="utf-8") as f:
            for stock_id in new_stocks:
                f.write(f"{stock_id}\n") # append尚未存在的股票代碼

        return f"✅ 已成功加入 {len(new_stocks)} 檔新股票：{', '.join(new_stocks)}"
    else:
        return "⚠️ 沒有新股票需要加入，或皆已存在於清單中。"
