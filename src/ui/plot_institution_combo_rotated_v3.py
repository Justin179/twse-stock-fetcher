import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

"""
圖示 外資與投信每日買賣超 + 持股比率 疊加呈現
v3：明確對 ax2 設定 xticks + xticklabels 解決旋轉無效問題
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

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

# 外資圖：買賣超 bar + 比率線（副軸）
colors_f = df["foreign_netbuy"].apply(lambda x: "red" if x > 0 else "green")
ax1.bar(df.index, df["foreign_netbuy"], color=colors_f)
ax1.set_ylabel("買賣超(張)")
ax1.grid(True, axis="y", linestyle="--", alpha=0.5)

ax1b = ax1.twinx()
ax1b.plot(df.index, df["foreign_ratio"], color="blue", marker='o', linewidth=1.5)
ax1b.set_ylabel("外資持股比率(%)")
ax1.set_title(f"{stock_id} 外資：買賣超 + 持股比率")

# 投信圖：買賣超 bar + 比率線（副軸）
colors_t = df["trust_netbuy"].apply(lambda x: "red" if x > 0 else "green")
ax2.bar(df.index, df["trust_netbuy"], color=colors_t)
ax2.set_ylabel("買賣超(張)")
ax2.grid(True, axis="y", linestyle="--", alpha=0.5)

ax2b = ax2.twinx()
ax2b.plot(df.index, df["trust_ratio"], color="purple", marker='o', linewidth=1.5)
ax2b.set_ylabel("投信持股比率(%)")
ax2.set_title(f"{stock_id} 投信：買賣超 + 持股比率")

# 明確設定 x 軸刻度與旋轉（作用在最下方子圖）
ax2.set_xticks(df.index)
ax2.set_xticklabels(df["date"].dt.strftime("%m-%d"), rotation=45, fontsize=8)

plt.tight_layout()
plt.show()