import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# 正確路徑
conn = sqlite3.connect("data/institution.db")

# 讀取 twse_prices 的成交量
df_twse = pd.read_sql_query("""
    SELECT date, volume FROM twse_prices
    WHERE stock_id = '2330'
    ORDER BY date
""", conn)
df_twse["date"] = pd.to_datetime(df_twse["date"])
df_twse.set_index("date", inplace=True)
df_twse.rename(columns={"volume": "TWSE_Volume"}, inplace=True)

# 讀取 yf_prices 的成交量
df_yf = pd.read_sql_query("""
    SELECT date, volume FROM yf_prices
    WHERE stock_id = '2330'
    ORDER BY date
""", conn)
conn.close()

df_yf["date"] = pd.to_datetime(df_yf["date"])
df_yf.set_index("date", inplace=True)
df_yf.rename(columns={"volume": "YF_Volume"}, inplace=True)

# 合併資料
df = pd.merge(df_twse, df_yf, left_index=True, right_index=True, how="inner")

# 差異欄位
df["差異"] = df["TWSE_Volume"] - df["YF_Volume"]

# 儲存成 CSV
df.to_csv("output/2330_volume_compare.csv", encoding="utf-8-sig")

# 繪圖
plt.figure(figsize=(12, 6))
plt.plot(df.index, df["TWSE_Volume"], label="TWSE 成交量")
plt.plot(df.index, df["YF_Volume"], label="Yahoo Finance 成交量")
plt.title("2330 成交量對比 (TWSE vs Yahoo Finance)")
plt.xlabel("日期")
plt.ylabel("成交量")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.xticks(rotation=45)
plt.show()