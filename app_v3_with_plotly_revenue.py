
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go

plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

# 讀取持股清單與公司名稱
def load_stock_list_with_names(file_path="my_stock_holdings.txt", db_path="data/institution.db"):
    with open(file_path, "r", encoding="utf-8") as f:
        stocks = sorted(line.strip() for line in f if line.strip())

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT stock_id, name FROM stock_meta", conn)
    conn.close()
    id_name_map = dict(zip(df["stock_id"].astype(str), df["name"]))

    display_options = [
        f"{stock_id} {id_name_map[stock_id]}" if stock_id in id_name_map else stock_id
        for stock_id in stocks
    ]
    return stocks, display_options

# 外資與投信圖
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
    ax1.set_title(f"{stock_id} 外資：買賣超 + 持股比率", fontsize=14)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.5)

    colors_t = df["trust_netbuy"].apply(lambda x: "red" if x > 0 else "green")
    ax2.bar(df.index, df["trust_netbuy"], color=colors_t)
    ax2b = ax2.twinx()
    ax2b.plot(df.index, df["trust_ratio"], color="purple", marker='o', linewidth=1.5)
    ax2.set_ylabel("買賣超(張)", fontsize=14)
    ax2b.set_ylabel("投信持股比率(%)", fontsize=14)
    ax2.set_title(f"{stock_id} 投信：買賣超 + 持股比率", fontsize=14)
    ax2.set_xticks(df.index)
    ax2.set_xticklabels(df["date"].apply(lambda d: f"{d.month}-{d.day}"), rotation=80, fontsize=12)
    ax2.grid(True, axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)

# 籌碼集中圖
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
    ax1b = ax1.twinx()
    ax1b.plot(x, df["avg_shares"], color="green", marker='o')

    ax2.set_title(f"{stock_id} 收盤價 vs 千張大戶持股比率", fontsize=14)
    ax2.plot(x, df["close_price"], color="red", marker='o')
    ax2b = ax2.twinx()
    ax2b.plot(x, df["ratio_1000"], color='blue', marker='o')

    ax2.set_xticks(x)
    ax2.set_xticklabels(x_labels, rotation=45, fontsize=12)
    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)

# Plotly 營收 + 年增率
def plot_monthly_revenue_plotly(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT * FROM monthly_revenue WHERE stock_id = ? ORDER BY year_month DESC LIMIT 36",
        conn, params=(stock_id,)
    )
    try:
        name_row = pd.read_sql_query(
            "SELECT name FROM stock_meta WHERE stock_id = ?", conn, params=(int(stock_id),)
        )
        stock_name = name_row.iloc[0]["name"] if not name_row.empty else ""
    except:
        stock_name = ""
    conn.close()

    if df.empty:
        st.warning(f"{stock_id} 無月營收資料")
        return

    df = df.sort_values("year_month")
    df["label"] = df["year_month"].astype(str).apply(lambda x: f"{x[2:4]}/{x[4:6]}")
    full_title = f"{stock_name} ({stock_id})"

    colors = ["red" if val >= 0 else "green" for val in df["yoy_rate"]]
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=df["label"],
        y=df["yoy_rate"],
        marker_color=colors,
        text=df["yoy_rate"].round(1).astype(str),
        textposition="outside",
        textangle=0,
        name="",
        hovertemplate="%{x}<br>%{y:.1f}%"
    ))
    fig1.update_layout(
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        showlegend=False,
        hoverlabel=dict(font=dict(size=16)),title=f"{full_title} 營收年增率", yaxis_title="營收年增率 (%)", height=400)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df["label"],
        y=df["revenue"],
        marker_color="brown",
        text=df["revenue"].round(0).astype(int).astype(str),
        textposition="outside",
        textangle=0,
        name="",
        hovertemplate="%{x}<br>%{y:.0f}"
    ))
    fig2.update_layout(
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        showlegend=False,
        hoverlabel=dict(font=dict(size=16)),title=f"{full_title} 營收", yaxis_title="營收 (百萬)", height=400)

    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig2, use_container_width=True)

# --- Streamlit ---
st.set_page_config(layout="wide")
st.title("📈 個股籌碼面、基本面")
with st.expander("📘 說明：這是什麼？"):
    st.markdown("""
    - 股票代碼清單來自 `my_stock_holdings.txt`
    - 自動更新資料至 `institution.db`
    - 圖表類型包含：
        - 外資 / 投信 買賣超與持股比率
        - 籌碼集中度與大戶比率
        - 月營收與年增率（互動圖）
    """)

col1, col2 = st.columns([1, 6])
with col1:
    stock_ids, stock_display = load_stock_list_with_names()
    selected_display = st.selectbox("股票代碼", stock_display)
    selected = selected_display.split()[0]

with col2:
    if selected:
        st.subheader("📊 法人買賣超 + 持股比率 (日)")
        plot_stock_institution(selected)
        st.subheader("📈 籌碼集中度 + 千張大戶持股比率 (週)")
        plot_holder_concentration(selected)
        st.subheader("📈 月營收 + 月營收年增率")
        plot_monthly_revenue_plotly(selected)
