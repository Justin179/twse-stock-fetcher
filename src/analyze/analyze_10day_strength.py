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
df["Close_5days_ago"] = df["Close"].shift(5)
df["High10"] = df["Close"].rolling(window=10).max()

# 判斷條件
analysis_days = df.tail(10).copy()
results = []

for _, row in analysis_days.iterrows():
    check = lambda b: "✅" if b else "❌"
    date = row["Date"].strftime("%Y-%m-%d")

    c1 = row["Close"] > row["Close_Yesterday"] and row["Volume"] > row["Volume_Yesterday"]
    c2 = row["Close"] > row["MA5"]
    c3 = row["Close"] > row["Close_5days_ago"]
    c4 = row["Close"] >= row["High10"]

    results.append({
        "日期": date,
        "價漲量增": check(c1),
        "站上5日均線": check(c2),
        "5日均線上彎": check(c3),
        "創10日新高": check(c4)
    })

# 轉置並簡化日期（月/日），條件名稱移到最後一欄
rotated = pd.DataFrame(results).set_index("日期").T
rotated.columns = [f"{datetime.strptime(c, "%Y-%m-%d").month}/{datetime.strptime(c, "%Y-%m-%d").day}" for c in rotated.columns]
rotated["條件名稱"] = rotated.index
rotated = rotated.reset_index(drop=True)
rotated = rotated[[col for col in rotated.columns if col != "條件名稱"] + ["條件名稱"]]

# 輸出
rotated.to_csv(f"output/{stock_id}_10day_strength.csv", index=False, encoding="utf-8-sig")
print(f"✅ 已輸出：output/{stock_id}_10day_strength.csv")
