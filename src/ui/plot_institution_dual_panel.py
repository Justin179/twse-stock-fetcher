import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

"""
圖示 TWSE 外資與投信每日買賣超資料(全上市公司)(60個交易日)
from institution_daily 資料表 
"""

stock_id = "3017"
conn = sqlite3.connect("data/institution.db")
df = pd.read_sql_query("""
    SELECT date, foreign_net_buy, trust_net_buy
    FROM institution_daily
    WHERE stock_id = ?
    ORDER BY date DESC
    LIMIT 60
""", conn, params=(stock_id,))
conn.close()

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)

# 外資圖
colors_f = df["foreign_net_buy"].apply(lambda x: "red" if x > 0 else "green")
ax1.bar(df.index, df["foreign_net_buy"], color=colors_f)
ax1.set_title(f"{stock_id} 外資買賣超")
ax1.grid(True, axis="y", linestyle="--", alpha=0.5)

# 投信圖
colors_t = df["trust_net_buy"].apply(lambda x: "red" if x > 0 else "green")
ax2.bar(df.index, df["trust_net_buy"], color=colors_t)
ax2.set_title(f"{stock_id} 投信買賣超")
ax2.grid(True, axis="y", linestyle="--", alpha=0.5)

# x 軸日期標籤
plt.xticks(df.index, df["date"].dt.strftime("%m-%d"), rotation=45)
plt.tight_layout()
plt.show()