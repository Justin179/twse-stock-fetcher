def apply_conditions(df, bias_threshold=3.0):
    
    # 計算 5 日前的收盤價（避免 apply 中做 shift）
    df["Close_5days_ago"] = df["Close"].shift(5)
    df["站上上彎5日均 且乖離小"] = df.apply(
        lambda row: (
            round((row["Close"] - row["MA5"]) / row["MA5"] * 100, 1) < bias_threshold
            and row["Close"] > row["MA5"]
            and row["Close"] > row["Close_5days_ago"]
        ),
        axis=1
    )

    df["均線排列正確 且開口小"] = (
        (df["MA5"] >= df["MA10"]) &
        (df["MA10"] >= df["MA24"]) &
        (((df["MA5"] - df["MA10"]) / df["MA10"]) * 100 < bias_threshold)
    )

    df["帶量跌"] = (df["Volume"] > df["Volume"].shift(1)) & (df["Close"] < df["Close"].shift(1))
    
    df["24日均乖離<15%"] = (
        (df["Close"] > df["MA24"]) &
        ((df["Close"] - df["MA24"]) / df["MA24"] * 100 < 15)
    )



    # 刪除輔助欄位，避免出現在輸出報告中
    df.drop(columns=["Close_5days_ago"], inplace=True)

    return df
