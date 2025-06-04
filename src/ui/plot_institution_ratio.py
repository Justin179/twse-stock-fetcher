import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

"""
圖示 外資與投信每日買賣超 + 持股比率 (近60個交易日)
from institutional_netbuy_holding 資料表
"""

stock_id = "3017"
conn = sqlite3.connect("data/institution.db")
df = pd.read_sql_query("""
    SELECT date, foreign_netbuy, trust_netbuy, foreign_ratio, trust_ratio
    FROM institutional_netbuy_holding
    WHERE stock_id = ?
    ORDER BY date DESC
    LIMIT 60
""", conn, params=(stock_id,))
conn.close()

# 資料整理
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

# 1. 外資買賣超
colors_f = df["foreign_netbuy"].apply(lambda x: "red" if x > 0 else "green")
ax1.bar(df.index, df["foreign_netbuy"], color=colors_f)
ax1.set_title(f"{stock_id} 外資買賣超 (張數)")
ax1.grid(True, axis="y", linestyle="--", alpha=0.5)

# 2. 投信買賣超
colors_t = df["trust_netbuy"].apply(lambda x: "red" if x > 0 else "green")
ax2.bar(df.index, df["trust_netbuy"], color=colors_t)
ax2.set_title(f"{stock_id} 投信買賣超 (張數)")
ax2.grid(True, axis="y", linestyle="--", alpha=0.5)

# 3. 外資持股比率
ax3.plot(df.index, df["foreign_ratio"], color="blue", marker='o', linewidth=1.5)
ax3.set_title("外資持股比率 (%)")
ax3.grid(True, linestyle="--", alpha=0.5)

# 4. 投信持股比率
ax4.plot(df.index, df["trust_ratio"], color="purple", marker='o', linewidth=1.5)
ax4.set_title("投信持股比率 (%)")
ax4.grid(True, linestyle="--", alpha=0.5)

# 日期 x 軸
plt.xticks(df.index, df["date"].dt.strftime("%m-%d"), rotation=45)
plt.tight_layout()
plt.show()