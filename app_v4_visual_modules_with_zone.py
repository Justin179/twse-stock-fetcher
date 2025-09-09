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
from ui.plot_eps_with_close_price import plot_eps_with_close_price
from ui.plot_profitability_ratios_final import plot_profitability_ratios_with_close_price
from common.login_helper import init_session_login_objects
from common.adding_new_stocks_helper import append_unique_stocks
import subprocess
from ui.collect_stock_button import render_collect_stock_button
from ui.show_temp_list_expander import render_temp_list_expander
from ui.bias_calculator import render_bias_calculator
from ui.peg_calculator import render_peg_calculator
from ui.volume_avg_calculator import render_volume_avg_calculator


plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

# --- Streamlit ---
st.set_page_config(page_title="法人主力買什麼?", layout="wide")
st.title("📈 技術線型(找已吃貨且還沒噴的) & 籌碼(守與拉的動機) & PEG")
with st.expander("📘 說明：這是什麼？"):
    st.markdown("""
    - **工作流程: 紅字加碼/鎖利-> 分析匯集精選股-> (三竹好股找機會 + 高分贏勢股)**
    - 股票代碼清單來自 `my_stock_holdings.txt`
    - 自動更新資料至 `institution.db`
    - **向上趨勢盤:** (1) 現價 過週高與月高  (2) 5_10_24均線上彎且多頭排列  (3) 現價站上5日均; 向下趨勢盤: 反向推論
    - **扣抵向下，唯一不能出現的情況是價跌量增(面對壓力變小還被賣下去，代表賣壓重)**; 扣抵向上，強勢股應盡快帶量向上攻擊，脫離扣抵值
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
    # 下拉選單區
    stock_ids, stock_display = load_stock_list_with_names(refresh=True)
    selected_display = st.selectbox("股票代碼", stock_display)
    selected = selected_display.split()[0]
    parts = selected_display.split()
    stock_display_reversed = f"{parts[1]} ({parts[0]})" if len(parts) == 2 else selected_display

    # 🔹 這一行就把整個功能帶進來（顯示在上方）
    render_collect_stock_button(
        source_files=["匯入XQ_rs90強勢股.csv","匯入XQ_籌碼集中度.csv","匯入XQ_過上月高點.csv","過上週上月高個股.csv"],
        temp_txt="temp_list.txt",
    )

    # 更新 temp_list 的股票(r_new_stocks_manual_setup.bat) & 加進持股清單(my_stock_holdings.txt)
    if st.button("➕ 更新 temp_list 的股票 & 加進持股清單"):
        # 非同步執行批次檔，不阻塞畫面
        subprocess.Popen("start r_new_stocks_manual_setup.bat", shell=True)
        msg = append_unique_stocks()
        st.success(msg)
        st.rerun()  # 🔁 直接重新跑整頁

    # …按鈕下面加一行：
    render_temp_list_expander(
        temp_txt="temp_list.txt",
        db_path="data/institution.db",
        title="📄 show temp_list"
    )

with col2:
    if selected:
        with st.expander("🧮 RSI / RS & 乖離率 / 成交量 / PEG 快算", expanded=False):
            col_left, col_mid, col_right = st.columns([2, 3, 3])
            with col_left:
                display_rs_rsi_info(selected)

            with col_mid:
                render_bias_calculator(key_suffix=selected, compact=True)
                render_volume_avg_calculator(key_suffix=selected, compact=True, default_days=5)

            with col_right:
                render_peg_calculator(selected, sdk=sdk, key_suffix=selected)

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
        
        st.subheader("📊 EPS & 三率 & 季收盤價 (20季)")
        try:
            fig_eps = plot_eps_with_close_price(selected)
            st.plotly_chart(fig_eps, use_container_width=True)
        except ValueError as e:
            st.warning(str(e))

        try:
            fig8 = plot_profitability_ratios_with_close_price(selected)
            st.plotly_chart(fig8, use_container_width=True)
        except ValueError as e:
            st.warning(str(e))