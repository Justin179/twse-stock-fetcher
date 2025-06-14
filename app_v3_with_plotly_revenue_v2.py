
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from src.ui.plot_price_interactive_final import plot_price_interactive
from src.ui.plot_institution_combo_plotly_final import plot_institution_combo_plotly
from src.ui.plot_holder_concentration_plotly_final import plot_holder_concentration_plotly
from src.ui.plot_monthly_revenue_with_close_cleaned_final_verified import plot_monthly_revenue_plotly

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
# 月營收&年增率圖表

# --- Streamlit ---
st.set_page_config(layout="wide")
st.title("📈 個股籌碼面、基本面")
with st.expander("📘 說明：這是什麼？"):
    st.markdown("""
    - 股票代碼清單來自 `my_stock_holdings.txt`
    - 自動更新資料至 `institution.db`
    - 圖表類型包含：
        - 收盤價互動圖（近60交易日）        
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
        st.subheader("📉 收盤價 (日)")
        fig_price = plot_price_interactive(selected)
        st.plotly_chart(fig_price, use_container_width=True)

        st.subheader("📊 法人買賣超 + 持股比率 (日)")
        fig1, fig2 = plot_institution_combo_plotly(selected)
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📈 籌碼集中度 & 千張大戶持股比率 (週)")
        fig3, fig4 = plot_holder_concentration_plotly(selected)
        st.plotly_chart(fig3, use_container_width=True)
        st.plotly_chart(fig4, use_container_width=True)

        st.subheader("📈 月營收年增率 & 月營收")
        fig5, fig6 = plot_monthly_revenue_plotly(selected)
        st.plotly_chart(fig5, use_container_width=True)
        st.plotly_chart(fig6, use_container_width=True)

