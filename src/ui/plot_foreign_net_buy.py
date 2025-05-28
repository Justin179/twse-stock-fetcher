import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 股票代號
stock_id = "3017"

# 連線資料庫
conn = sqlite3.connect("data/institution.db")
df = pd.read_sql_query("""
    SELECT date, foreign_net_buy 
    FROM institution_daily
    WHERE stock_id = ?
    ORDER BY date DESC
    LIMIT 20
""", conn, params=(stock_id,))
conn.close()

# 資料處理
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")

# 畫圖：紅上綠下
plt.figure(figsize=(12, 5))
colors = df["foreign_net_buy"].apply(lambda x: "red" if x > 0 else "green")
plt.bar(df["date"], df["foreign_net_buy"], color=colors)

# 格式化日期
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
plt.xticks(rotation=45)

# 標題與格線
plt.title(f"{stock_id} 外資近 20 日買賣超")
plt.ylabel("張數")
plt.grid(True, axis="y", linestyle="--", alpha=0.5)
plt.tight_layout()
plt.show()