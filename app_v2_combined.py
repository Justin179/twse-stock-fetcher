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

# 畫外資/投信圖表
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

# 畫籌碼集中度圖表
def plot_holder_concentration(stock_id):
    conn = sqlite3.connect("data/institution.db")
    df = pd.read_sql_query("""
        SELECT * FROM holder_concentration
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT 26
    """, conn, params=(stock_id,))
    conn.close()

    df = df.sort_values(by="date")
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    x_labels = df["date"].dt.strftime("%m-%d")
    x = range(len(df))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), dpi=100, sharex=True)

    ax1.set_title(f"{stock_id} 收盤價 vs 籌碼集中度")
    ax1.plot(x, df["close_price"], color="red", marker='o')
    ax1.set_ylabel("收盤價", color="red")
    ax1.tick_params(axis='y', labelcolor="red")

    ax1b = ax1.twinx()
    ax1b.plot(x, df["avg_shares"], color="green", marker='o')
    ax1b.set_ylabel("籌碼集中度 (張)", color="green")
    ax1b.tick_params(axis='y', labelcolor="green")

    ax2.set_title(f"{stock_id} 收盤價 vs 千張大戶持股比率")
    ax2.plot(x, df["close_price"], color="red", marker='o')
    ax2.set_ylabel("收盤價", color="red")
    ax2.tick_params(axis='y', labelcolor="red")

    ax2b = ax2.twinx()
    ax2b.plot(x, df["ratio_1000"], color='blue', marker='o')
    ax2b.set_ylabel("千張大戶持股比率 (%)", color='blue')
    ax2b.tick_params(axis='y', labelcolor='blue')

    ax2.set_xticks(x)
    ax2.set_xticklabels(x_labels, rotation=45, fontsize=8)

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)

# Streamlit UI
st.set_page_config(layout="wide")
st.title("📈 法人買賣超與籌碼集中圖表")
with st.expander("📘 說明：這是什麼？"):
    st.markdown("""
    - 股票代碼清單來自 `my_stock_holdings.txt`
    - 自動更新資料至 `institution.db`
    - 包含兩種圖表：
        - 外資 / 投信 買賣超與持股比率
        - 籌碼集中度與千張大戶持股比率
    """)

col1, col2 = st.columns([1, 6])

with col1:
    stock_list = load_stock_list()
    selected = st.selectbox("股票代碼", stock_list)

with col2:
    if selected:
        st.subheader("📊 法人買賣超 + 持股比率")
        plot_stock_institution(selected)
        st.subheader("📈 籌碼集中度 + 千張大戶持股比率")
        plot_holder_concentration(selected)
