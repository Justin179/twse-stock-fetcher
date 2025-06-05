import sqlite3
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.font_manager as fm
import pandas as pd

# 設定字型避免中文亂碼
plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

# 參數設定
stock_id = "3017"
db_path = "data/institution.db"

# 連線與查詢
conn = sqlite3.connect(db_path)
df = pd.read_sql_query(f'''
    SELECT * FROM holder_concentration
    WHERE stock_id = "{stock_id}"
    ORDER BY date DESC
    LIMIT 26
''', conn)
conn.close()

df = df.sort_values(by="date")
df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")

# x軸日期標籤轉為 "MM-DD" 格式
x_labels = df["date"].dt.strftime("%m-%d")
x = range(len(df))

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# ---- 第一張圖：收盤價 vs 籌碼集中度 ----
color1 = 'tab:red'
color2 = 'tab:green'
ax1.set_title(f"{stock_id} 收盤價 vs 籌碼集中度")
ax1.plot(x, df["close_price"], color=color1, marker='o', label="收盤價")
ax1.set_ylabel("收盤價", color=color1)
ax1.tick_params(axis='y', labelcolor=color1)

ax1b = ax1.twinx()
ax1b.plot(x, df["avg_shares"], color=color2, marker='o', label="籌碼集中度")
ax1b.set_ylabel("籌碼集中度 (張)", color=color2)
ax1b.tick_params(axis='y', labelcolor=color2)

# ---- 第二張圖：收盤價 vs 大戶持股比率 ----
ax2.set_title(f"{stock_id} 收盤價 vs 千張大戶持股比率")
ax2.plot(x, df["close_price"], color=color1, marker='o', label="收盤價")
ax2.set_ylabel("收盤價", color=color1)
ax2.tick_params(axis='y', labelcolor=color1)

ax2b = ax2.twinx()
ax2b.plot(x, df["ratio_1000"], color='tab:blue', marker='o', label=">1000張佔比")
ax2b.set_ylabel("千張大戶持股比率 (%)", color='tab:blue')
ax2b.tick_params(axis='y', labelcolor='tab:blue')

# 設定 x 軸
plt.xticks(x, x_labels, rotation=45)

plt.tight_layout()
plt.show()
