import pandas as pd
from datetime import datetime

# 設定股票代號
stock_id = "2330"
df = pd.read_csv(f"data/{stock_id}_history.csv")
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

# 計算欄位
df["Close_Yesterday"] = df["Close"].shift(1)
df["Volume_Yesterday"] = df["Volume"].shift(1)
df["MA5"] = df["Close"].rolling(window=5).mean()
df["MA10"] = df["Close"].rolling(window=10).mean()
df["MA24"] = df["Close"].rolling(window=24).mean()

df["Close_4days_ago"] = df["Close"].shift(4)
df["Close_5days_ago"] = df["Close"].shift(5)
df["Close_10days_ago"] = df["Close"].shift(10)
df["Close_24days_ago"] = df["Close"].shift(24)

df["High10"] = df["Close"].rolling(window=10).max()

# 計算 KD（RSV）
low9 = df["Close"].rolling(window=9).min()
high9 = df["Close"].rolling(window=9).max()
rsv = (df["Close"] - low9) / (high9 - low9) * 100
df["K"] = rsv.ewm(com=2).mean()
df["D"] = df["K"].ewm(com=2).mean()
df["K_prev"] = df["K"].shift(1)
df["D_prev"] = df["D"].shift(1)

# 計算 RSI14
delta = df["Close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.rolling(window=14).mean()
avg_loss = loss.rolling(window=14).mean()
rs = avg_gain / avg_loss
df["RSI"] = 100 - (100 / (1 + rs))
df["RSI_Yesterday"] = df["RSI"].shift(1)

# 判斷條件
analysis_days = df.tail(10).copy()
results = []

for _, row in analysis_days.iterrows():
    check = lambda b: "✅" if b else "❌"
    date = row["Date"].strftime("%Y-%m-%d")

    c1 = (
        (row["Close"] > row["Close_Yesterday"] and row["Volume"] > row["Volume_Yesterday"]) or
        (row["Close"] < row["Close_Yesterday"] and row["Volume"] < row["Volume_Yesterday"])
    )
    c2 = row["Close"] > row["MA5"]
    c3 = row["Close"] > row["Close_5days_ago"]
    c4 = row["Close"] >= row["High10"]
    c5 = row["MA5"] > row["MA10"] > row["MA24"]
    c6 = (
        row["Close"] > row["Close_5days_ago"]
        and row["Close"] > row["Close_10days_ago"]
        and row["Close"] > row["Close_24days_ago"]
    )
    c7 = (
        row["Close_4days_ago"] > row["Close_5days_ago"] and
        row["Close"] > row["Close_Yesterday"] and
        row["Volume"] > row["Volume_Yesterday"]
    )
    c8 = (
        row["K"] > row["D"] and
        row["K_prev"] < row["D_prev"] and
        row["K"] < 50
    )
    c9 = (
        row["RSI"] > row["RSI_Yesterday"] and
        row["RSI_Yesterday"] < 45 and
        row["RSI"] > 30
    )

    results.append({
        "日期": date,
        "價漲量增or價跌量縮": check(c1),
        "站上5日均線": check(c2),
        "5日均線上彎": check(c3),
        "創10日新高": check(c4),
        "短中均線多頭排列": check(c5),
        "短中均線皆上彎": check(c6),
        "明壓變大但價漲量增": check(c7),
        "KD 金叉（低檔）": check(c8),
        "RSI 低檔翻揚": check(c9)
    })

# 轉置輸出
rotated = pd.DataFrame(results).set_index("日期").T
rotated.columns = [f"{datetime.strptime(c, "%Y-%m-%d").month}/{datetime.strptime(c, "%Y-%m-%d").day}" for c in rotated.columns]
rotated["條件名稱"] = rotated.index
rotated = rotated.reset_index(drop=True)
rotated = rotated[[col for col in rotated.columns if col != "條件名稱"] + ["條件名稱"]]

# 輸出 CSV
rotated.to_csv(f"output/{stock_id}_10day_strength.csv", index=False, encoding="utf-8-sig")
print(f"✅ 已輸出：output/{stock_id}_10day_strength.csv")
