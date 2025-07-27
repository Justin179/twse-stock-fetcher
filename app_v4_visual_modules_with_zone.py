import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from common.stock_loader import load_stock_list_with_names
from ui.price_break_display_module import display_price_break_analysis
from ui.plot_price_position_zone import plot_price_position_zone
from ui.rs_rsi_display_module import display_rs_rsi_info
from ui.plot_strength_table import analyze_10day_strength
import plotly.graph_objects as go
from ui.plot_price_interactive_final import plot_price_interactive
from ui.plot_institution_combo_plotly_final import plot_institution_combo_plotly
from ui.plot_main_force_plotly_final import plot_main_force_charts
from ui.plot_holder_concentration_plotly_final import plot_holder_concentration_plotly
from ui.plot_monthly_revenue_with_close_on_left_final import plot_monthly_revenue_plotly
from ui.plot_profitability_ratios_final import plot_profitability_ratios_with_close_price
from common.login_helper import init_session_login_objects
from common.adding_new_stocks_helper import append_unique_stocks

plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

# --- Streamlit ---
st.set_page_config(layout="wide")
st.title("📈 個股 技術 & 籌碼(守與拉的動機)")
with st.expander("📘 說明：這是什麼？"):
    st.markdown("""
    - 股票代碼清單來自 `my_stock_holdings.txt`
    - 自動更新資料至 `institution.db`
    - **扣下，唯一不能出現的情況是價跌量增**; 扣上，強勢股應盡快帶量向上攻擊，脫離扣抵值
    - 圖表類型包含：
        - RS / RSI 評分 (RS>90 強勢股、RSI>70 超買 RSI<30 超賣)(每晚的10:50 更新最新排名)
        - 每日收盤價
        - 外資 / 投信 買賣超與持股比率 (日)
        - 主力買賣超與買賣家數差 (日)       
        - 籌碼集中度與大戶比率 (週)
        - 月營收與年增率 (月)
        - 三率（毛利率、營業利益率、稅後淨利率）與季收盤價 (季)        
    """)


sdk, dl = init_session_login_objects()


col1, col2 = st.columns([1, 6])
with col1:
    stock_ids, stock_display = load_stock_list_with_names()
    selected_display = st.selectbox("股票代碼", stock_display)
    selected = selected_display.split()[0]
    parts = selected_display.split()
    stock_display_reversed = f"{parts[1]} ({parts[0]})" if len(parts) == 2 else selected_display

    if st.button("➕ 將 temp_list.txt 中的新股票加入持股清單"):
        msg = append_unique_stocks()
        st.success(msg)


with col2:
    if selected:
        # 顯示 RS / RSI 數值
        display_rs_rsi_info(selected)
        st.subheader("📌 關鍵價位分析")
        result = display_price_break_analysis(selected, dl=dl, sdk=sdk)
        if result:
            today_date, c1, o, c2, h, l, w1, w2, m1, m2 = result
        
        st.subheader("📌 現價與區間關係視覺化")
        fig_zone = plot_price_position_zone(stock_display_reversed, today_date, c1, o, c2, h, l, w1, w2, m1, m2)
        st.plotly_chart(fig_zone, use_container_width=True)
        
        st.markdown(f"""
        <span style='font-size:22px'>📋 短線條件分析表格 (近10日)</span>
        <span style='font-size:16px; color:gray'>　{selected_display}</span>
        """, unsafe_allow_html=True)
        fig_strength = analyze_10day_strength(selected)
        st.plotly_chart(fig_strength, use_container_width=True, config={"displayModeBar": False})

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