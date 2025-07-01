import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from src.ui.plot_price_interactive_final import plot_price_interactive
from src.ui.plot_institution_combo_plotly_final import plot_institution_combo_plotly
from src.ui.plot_main_force_plotly_final import plot_main_force_charts
from src.ui.plot_holder_concentration_plotly_final import plot_holder_concentration_plotly
from src.ui.plot_monthly_revenue_with_close_on_left_final import plot_monthly_revenue_plotly
from src.ui.plot_profitability_ratios_final import plot_profitability_ratios_with_close_price

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

# 讀取個股 RS / RSI 評分資訊
def fetch_rs_rsi_info(stock_id: str, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    query = f"""
        SELECT return_1y, rs_score_1y, return_ytd, rs_score_ytd, rsi14, updated_at
        FROM stock_rs_rsi
        WHERE stock_id = ?
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()
    return df.iloc[0] if not df.empty else None

# --- Streamlit ---
st.set_page_config(layout="wide")
st.title("📈 個股籌碼面、基本面")
with st.expander("📘 說明：這是什麼？"):
    st.markdown("""
    - 股票代碼清單來自 `my_stock_holdings.txt`
    - 自動更新資料至 `institution.db`
    - 圖表類型包含：
        - RS / RSI 評分 (RS>90 強勢股、RSI>70 超買 RSI<30 超賣)
        - 每日收盤價
        - 外資 / 投信 買賣超與持股比率 (日)
        - 主力買賣超與買賣家數差 (日)       
        - 籌碼集中度與大戶比率 (週)
        - 月營收與年增率 (月)
        - 三率（毛利率、營業利益率、稅後淨利率）與季收盤價 (季)        
    """)

col1, col2 = st.columns([1, 6])
with col1:
    stock_ids, stock_display = load_stock_list_with_names()
    selected_display = st.selectbox("股票代碼", stock_display)
    selected = selected_display.split()[0]

with col2:
    if selected:
        # 顯示 RS / RSI 數值
        rs_info = fetch_rs_rsi_info(selected)
        if rs_info is not None:
            st.markdown("### 📌 RSI / RS 概況")
            st.markdown(f"""
            - **RS分數 (1Y)**：{rs_info['rs_score_1y']} {'🔥 強勢股' if rs_info['rs_score_1y'] >= 90 else ''}
            - **RS分數 (YTD)**：{rs_info['rs_score_ytd']} {'🔥 強勢股' if rs_info['rs_score_ytd'] >= 90 else ''}
            - **RSI(14)**：{rs_info['rsi14']} {'⚠️ 超買' if rs_info['rsi14'] > 70 else ('🔻 超賣' if rs_info['rsi14'] < 30 else '')}
            - **更新日期**：{rs_info['updated_at']}
            """)
        else:
            st.warning("⚠️ 找不到該股票的 RSI / RS 評分資料。")

        st.subheader("📉 收盤價 (日)")
        fig_price = plot_price_interactive(selected)
        st.plotly_chart(fig_price, use_container_width=True)

        st.subheader("📊 法人買賣超 & 持股比率 (日)")
        fig1, fig2 = plot_institution_combo_plotly(selected)
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📈 主力買賣超 & 買賣家數差 (日)")
        fig_main1, fig_main2 = plot_main_force_charts(selected)
        st.plotly_chart(fig_main1, use_container_width=True)
        st.plotly_chart(fig_main2, use_container_width=True)

        st.subheader("📈 籌碼集中度 & 千張大戶持股比率 (週)")
        fig3, fig4 = plot_holder_concentration_plotly(selected)
        st.plotly_chart(fig3, use_container_width=True)
        st.plotly_chart(fig4, use_container_width=True)

        st.subheader("📈 營收年增率 & 月營收 & 營收月增率")
        fig5, fig6, fig7 = plot_monthly_revenue_plotly(selected)
        st.plotly_chart(fig5, use_container_width=True)
        st.plotly_chart(fig6, use_container_width=True)
        st.plotly_chart(fig7, use_container_width=True)

        st.subheader("📊 三率 & 季收盤價 (20季)")
        try:
            fig8 = plot_profitability_ratios_with_close_price(selected)
            st.plotly_chart(fig8, use_container_width=True)
        except ValueError as e:
            st.warning(str(e))
