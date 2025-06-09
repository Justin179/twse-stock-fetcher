
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from src.ui.plot_institution_combo_plotly_fixed_functional import plot_institution_combo_plotly
from src.ui.plot_holder_concentration_plotly_fixed_functional import plot_holder_concentration_plotly

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


# 法人買賣超圖表
# 籌碼集中度圖表

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
        - 外資 / 投信 買賣超與持股比率（互動式）
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
        fig1, fig2 = plot_institution_combo_plotly(selected, "data/institution.db")
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📈 籌碼集中度 + 千張大戶持股比率 (週)")
        fig3, fig4 = plot_holder_concentration_plotly(selected, "data/institution.db")
        st.plotly_chart(fig3, use_container_width=True)
        st.plotly_chart(fig4, use_container_width=True)

        st.subheader("📈 月營收 + 月營收年增率")
        plot_monthly_revenue_plotly(selected)
