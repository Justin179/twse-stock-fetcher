def apply_conditions(df, bias_threshold=2.0):
    
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

    df["5 10 24均線上彎 多頭排列 開口小"] = (
        (df["MA5"] >= df["MA10"]) &
        (df["MA10"] >= df["MA24"]) &
        (((df["MA5"] - df["MA10"]) / df["MA10"]) * 100 < bias_threshold) &
        (df["Close"] > df["Close"].shift(10)) & # 10日均線上彎
        (df["Close"] > df["Close"].shift(24)) # 24日均線上彎
    )

    df["24日均乖離<15%"] = (
        (df["Close"] > df["MA24"]) &
        ((df["Close"] - df["MA24"]) / df["MA24"] * 100 < 15) 
    )

    df["量價同步"] = (
        ((df["Volume"] > df["Volume"].shift(1)) & (df["Close"] > df["Close"].shift(1))) |
        ((df["Volume"] < df["Volume"].shift(1)) & (df["Close"] < df["Close"].shift(1)))
    )

    # df["上彎72日均"] = (df["Close"] > df["Close"].shift(72))

    # df["站上72日均"] = df["Close"] > df["MA72"]

    df["站上上彎72日均"] = (
        (df["Close"] > df["Close"].shift(72)) &
        (df["Close"] > df["MA72"])
    )



    # df["接近72或200日均線壓力"] = (
    #     (
    #         (df["Close"] < df["Close"].shift(72)) &
    #         (df["MA72"] > df["Close"]) &
    #         ((df["MA72"] - df["Close"]) / df["Close"]) * 100 < 3
    #     ) |
    #     (
    #         (df["Close"] < df["Close"].shift(200)) &  # 200日均線下彎
    #         (df["MA200"] > df["Close"]) &             # 價格在200日均線下方
    #         ((df["MA200"] - df["Close"]) / df["Close"]) * 100 < 3  # 接近
    #     )
    # )


    # 刪除輔助欄位，避免出現在輸出報告中
    df.drop(columns=["Close_5days_ago"], inplace=True)

    return df
