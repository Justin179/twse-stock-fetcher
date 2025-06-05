import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

# 讀取持股清單
def load_stock_list(file_path="my_stock_holdings.txt"):
    with open(file_path, "r", encoding="utf-8") as f:
        stocks = sorted(line.strip() for line in f if line.strip())
    return stocks

# 畫圖主邏輯
def plot_stock_institution(stock_id):
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

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), dpi=100, sharex=True)

    colors_f = df["foreign_netbuy"].apply(lambda x: "red" if x > 0 else "green")
    ax1.bar(df.index, df["foreign_netbuy"], color=colors_f)
    ax1b = ax1.twinx()
    ax1b.plot(df.index, df["foreign_ratio"], color="blue", marker='o', linewidth=1.5)
    ax1.set_ylabel("買賣超(張)")
    ax1b.set_ylabel("外資持股比率(%)")
    ax1.set_title(f"{stock_id} 外資：買賣超 + 持股比率")
    ax1.grid(True, axis="y", linestyle="--", alpha=0.5)

    colors_t = df["trust_netbuy"].apply(lambda x: "red" if x > 0 else "green")
    ax2.bar(df.index, df["trust_netbuy"], color=colors_t)
    ax2b = ax2.twinx()
    ax2b.plot(df.index, df["trust_ratio"], color="purple", marker='o', linewidth=1.5)
    ax2.set_ylabel("買賣超(張)")
    ax2b.set_ylabel("投信持股比率(%)")
    ax2.set_title(f"{stock_id} 投信：買賣超 + 持股比率")
    ax2.set_xticks(df.index)
    ax2.set_xticklabels(df["date"].dt.strftime("%m-%d"), rotation=45, fontsize=8)
    ax2.grid(True, axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)

# Streamlit UI
st.set_page_config(layout="wide")
st.title("📈 法人買賣超圖表系統")

col1, col2 = st.columns([1, 6])

with col1:
    stock_list = load_stock_list()
    selected = st.selectbox("股票代碼", stock_list)

with col2:
    if selected:
        plot_stock_institution(selected)