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
    ax1.set_ylabel("買賣超(張)", fontsize=14)
    ax1b.set_ylabel("外資持股比率(%)", fontsize=14)
    ax1.yaxis.set_tick_params(labelsize=12)
    ax1b.yaxis.set_tick_params(labelsize=12)
    ax1.set_title(f"{stock_id} 外資：買賣超 + 持股比率", fontsize=14)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.5)

    colors_t = df["trust_netbuy"].apply(lambda x: "red" if x > 0 else "green")
    ax2.bar(df.index, df["trust_netbuy"], color=colors_t)
    ax2b = ax2.twinx()
    ax2b.plot(df.index, df["trust_ratio"], color="purple", marker='o', linewidth=1.5)
    ax2.set_ylabel("買賣超(張)", fontsize=14)
    ax2b.set_ylabel("投信持股比率(%)", fontsize=14)
    ax2.yaxis.set_tick_params(labelsize=12)
    ax2b.yaxis.set_tick_params(labelsize=12)
    ax2.set_title(f"{stock_id} 投信：買賣超 + 持股比率", fontsize=14)
    ax2.set_xticks(df.index)
    ax2.set_xticklabels(df["date"].apply(lambda d: f"{d.month}-{d.day}"), rotation=80, fontsize=12)
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
    x_labels = df["date"].apply(lambda d: f"{d.month}-{d.day}")
    x = range(len(df))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), dpi=100, sharex=True)

    ax1.set_title(f"{stock_id} 收盤價 vs 籌碼集中度", fontsize=14)
    ax1.plot(x, df["close_price"], color="red", marker='o')
    ax1.set_ylabel("收盤價", color="red", fontsize=14)
    ax1.tick_params(axis='y', labelcolor="red", labelsize=14)

    ax1b = ax1.twinx()
    ax1b.plot(x, df["avg_shares"], color="green", marker='o')
    ax1b.set_ylabel("籌碼集中度 (張)", color="green", fontsize=14)
    ax1b.tick_params(axis='y', labelcolor="green", labelsize=14)

    ax2.set_title(f"{stock_id} 收盤價 vs 千張大戶持股比率", fontsize=14)
    ax2.plot(x, df["close_price"], color="red", marker='o')
    ax2.set_ylabel("收盤價", color="red", fontsize=14)
    ax2.tick_params(axis='y', labelcolor="red", labelsize=14)

    ax2b = ax2.twinx()
    ax2b.plot(x, df["ratio_1000"], color='blue', marker='o')
    ax2b.set_ylabel("千張大戶持股比率 (%)", color='blue', fontsize=14)
    ax2b.tick_params(axis='y', labelcolor='blue', labelsize=14)

    ax2.set_xticks(x)
    ax2.set_xticklabels(x_labels, rotation=45, fontsize=12)

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)

# 畫月營收圖表
def plot_monthly_revenue(stock_id):
    conn = sqlite3.connect("data/institution.db")
    df = pd.read_sql_query(
        """
        SELECT * FROM monthly_revenue
        WHERE stock_id = ?
        ORDER BY year_month DESC
        LIMIT 24
        """, conn, params=(stock_id,)
    )
    conn.close()

    if df.empty:
        st.warning(f"{stock_id} 無月營收資料")
        return

    df = df.sort_values("year_month")
    df["label"] = df["year_month"].astype(str).str.slice(2)
    x = range(len(df))

    fig, ax1 = plt.subplots(figsize=(16, 6), dpi=100)
    ax1.bar(x, df["revenue"], color="orange", label="月營收")
    ax1.set_ylabel("月營收 (百萬)", color="orange", fontsize=14)
    ax1.tick_params(axis="y", labelcolor="orange", labelsize=14)

    ax2 = ax1.twinx()
    ax2.plot(x, df["yoy_rate"], color="blue", marker="o", label="年增率")
    ax2.set_ylabel("年增率 (%)", color="blue", fontsize=14)
    ax2.tick_params(axis="y", labelcolor="blue", labelsize=14)

    ax1.set_xticks(x)
    ax1.set_xticklabels(df["label"], rotation=0, fontsize=12)
    plt.title(f"{stock_id} 月營收與年增率 (近24個月)", fontsize=14)
    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)

# Streamlit UI
st.set_page_config(layout="wide")
st.title("📈 個股籌碼面、基本面")
with st.expander("📘 說明：這是什麼？"):
    st.markdown("""
    - 股票代碼清單來自 `my_stock_holdings.txt`
    - 自動更新資料至 `institution.db`
    - 圖表類型包含：
        - 外資 / 投信 買賣超與持股比率
        - 籌碼集中度與大戶比率
        - 月營收與年增率
    """)

col1, col2 = st.columns([1, 6])

with col1:
    stock_list = load_stock_list()
    selected = st.selectbox("股票代碼", stock_list)

with col2:
    if selected:
        st.subheader("📊 法人買賣超 + 持股比率 (日)")
        plot_stock_institution(selected)
        st.subheader("📈 籌碼集中度 + 千張大戶持股比率 (週)")
        plot_holder_concentration(selected)
        st.subheader("📈 月營收 + 年增率 (月)")
        plot_monthly_revenue(selected)
