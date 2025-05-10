def apply_conditions(df, bias_threshold=3.0):
    df["站上5日均 且乖離小"] = df.apply(
        lambda row: round((row["Close"] - row["MA5"]) / row["MA5"] * 100, 1) < bias_threshold
        if row["Close"] > row["MA5"] else False,
        axis=1
    )

    df["均線排列正確 且開口小"] = (
        (df["MA5"] >= df["MA10"]) &
        (df["MA10"] >= df["MA24"]) &
        (((df["MA5"] - df["MA10"]) / df["MA10"]) * 100 < bias_threshold)
    )

    df["帶量跌"] = (df["Volume"] > df["Volume"].shift(1)) & (df["Close"] < df["Close"].shift(1))
    
    return df
