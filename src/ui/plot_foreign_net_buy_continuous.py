import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

stock_id = "3017"
conn = sqlite3.connect("data/institution.db")
df = pd.read_sql_query("""
    SELECT date, foreign_net_buy 
    FROM institution_daily
    WHERE stock_id = ?
    ORDER BY date DESC
    LIMIT 20
""", conn, params=(stock_id,))
conn.close()

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

# 改用 index 作為 x 軸，避免假日空白
plt.figure(figsize=(12, 5))
colors = df["foreign_net_buy"].apply(lambda x: "red" if x > 0 else "green")
plt.bar(df.index, df["foreign_net_buy"], color=colors)

# 用 index 對應日期當作 xtick label
plt.xticks(df.index, df["date"].dt.strftime("%Y-%m-%d"), rotation=45)

plt.title(f"{stock_id} 外資近 20 日買賣超（連續 K 線）")
plt.ylabel("張數")
plt.grid(True, axis="y", linestyle="--", alpha=0.5)
plt.tight_layout()
plt.show()