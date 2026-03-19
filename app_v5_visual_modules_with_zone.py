import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
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
from common.shared_stock_selector import save_selected_stock, get_last_selected_or_default
import subprocess
from ui.collect_stock_button import render_collect_stock_button
from ui.show_temp_list_expander import render_temp_list_expander
from ui.bias_calculator import render_bias_calculator
from ui.peg_calculator import render_peg_calculator
from ui.volume_avg_calculator import render_volume_avg_calculator
from common.futures_spread_helper import get_futures_spread_info, format_futures_spread_display
from tools.t2_settlement_tracker import render_t2_settlement_tracker


plt.rcParams['font.family'] = 'Microsoft JhengHei'
plt.rcParams['axes.unicode_minus'] = False

# --- Streamlit ---
st.set_page_config(page_title="量價趨勢 主力確認, eps上修", layout="wide")

# 🔹 在頁面最頂部放一個錨點
st.markdown('<div id="top"></div>', unsafe_allow_html=True)

# 🔹 加入「回到頂部」浮動按鈕 - 使用 HTML anchor 方式
st.markdown("""
<style>
    .back-to-top {
        position: fixed;
        bottom: 30px;
        right: 30px;
        z-index: 9999;
        background-color: #E8E8E8;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 32px;
        font-weight: bold;
        text-decoration: none;
        box-shadow: 0 6px 12px rgba(0,0,0,0.4);
        transition: all 0.3s ease;
        border: 3px solid #1f77b4;
        color: #1f77b4;
    }
    .back-to-top:hover {
        background-color: #D0D0D0;
        transform: scale(1.15);
        box-shadow: 0 8px 16px rgba(0,0,0,0.5);
        color: #0d5a8f;
    }
</style>
<a href="#top" class="back-to-top" title="回到頂部">⬆</a>
""", unsafe_allow_html=True)


sdk, dl = init_session_login_objects()


def trigger_main_force_update(stock_id: str) -> None:
    cmd = f"start /min python src\\tools\\update_single_stock_main_force.py {stock_id}"
    subprocess.Popen(cmd, shell=True)
    st.session_state[f"show_update_msg_{stock_id}"] = True


def trigger_institutional_update(stock_id: str) -> None:
    cmd = f"start /min python src\\tools\\update_single_stock_institutional.py {stock_id}"
    subprocess.Popen(cmd, shell=True)
    st.session_state[f"show_update_msg_inst_{stock_id}"] = True


col1, col2 = st.columns([1, 6])
with col1:
    # 🔹 期現價差資訊（添加在股票代碼選單上方）
    with st.expander("📊 台指期現價差", expanded=False):
        futures_data = get_futures_spread_info()
        spread_display = format_futures_spread_display(futures_data)
        st.markdown(spread_display)
    
    # 下拉選單區
    stock_ids, stock_display = load_stock_list_with_names(refresh=True)
    
    # 🔹 使用 session_state 來追蹤當前股票，避免被共享檔案覆蓋
    if "current_stock_id" not in st.session_state:
        # 首次載入：從共享檔案讀取
        initial_stock = get_last_selected_or_default(default="2330")
        st.session_state["current_stock_id"] = initial_stock
    
    # 找到當前股票在清單中的位置
    current_stock = st.session_state["current_stock_id"]
    default_index = 0
    for idx, display in enumerate(stock_display):
        if display.startswith(current_stock + " "):
            default_index = idx
            break
    
    # 使用 on_change 回調來處理變更
    def on_stock_change():
        selected_display = st.session_state["stock_selector"]
        new_stock = selected_display.split()[0]
        # 更新 session_state
        st.session_state["current_stock_id"] = new_stock
        # 儲存到共享檔案
        save_selected_stock(new_stock)
    
    selected_display = st.selectbox(
        "股票代碼", 
        stock_display, 
        index=default_index, 
        key="stock_selector",
        on_change=on_stock_change
    )
    selected = selected_display.split()[0]
    
    parts = selected_display.split()
    stock_display_reversed = f"{parts[1]} ({parts[0]})" if len(parts) == 2 else selected_display

    # 🔹 這一行就把整個功能帶進來（顯示在上方）
    render_collect_stock_button(
        source_files=["匯入XQ_rs90強勢股.csv","匯入XQ_籌碼集中度.csv","匯入XQ_過上月高點.csv","籌碼集中且趨勢向上.csv"],
        temp_txt="temp_list.txt",
    )

    # 更新 temp_list 的股票(r_new_stocks_manual_setup.bat) & 加進持股清單(my_stock_holdings.txt)
    if st.button("➕ 更新 temp_list 的股票 & 加進持股清單"):
        # 非同步執行批次檔，不阻塞畫面
        subprocess.Popen("start r_new_stocks_manual_setup.bat", shell=True)
        msg = append_unique_stocks()
        st.success(msg)
        st.rerun()  # 🔁 直接重新跑整頁

    # 🔹 插入提示文字（藍圈位置）
    st.markdown(
        """
        <div style='text-align: center; font-size: 18px; font-weight: 500; margin-top: -4px; margin-bottom: 10px; line-height: 1.2;'>
            <span style='color: #ff4b4b; font-family: "DFKai-SB", "KaiTi", "STKaiti", "Segoe Script", "Comic Sans MS", cursive; font-size: 20px; font-weight: 550;'>看多做多🗡️順勢而為</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 🔹 左側快捷更新（免捲動到下方）
    quick_col1, quick_col2 = st.columns(2)
    with quick_col1:
        if st.button("🔄 主力", key=f"sidebar_update_main_force_{selected}", use_container_width=True):
            trigger_main_force_update(selected)
    with quick_col2:
        if st.button("🔄 外資", key=f"sidebar_update_institutional_{selected}", use_container_width=True):
            trigger_institutional_update(selected)
    
    # 🔹 當前週數顯示
    today = datetime.now()
    year, week_num, weekday = today.isocalendar()

    # 🔹 月初/月中標註（依日曆日）
    month_phase_tag = ""
    if 1 <= today.day <= 5:
        month_phase_tag = ", 月初基"
    elif 16 <= today.day <= 20:
        month_phase_tag = ", 月中贏"

    st.markdown(f"""
    <div style='text-align: center; padding: 8px; background-color: #f0f2f6; border-radius: 5px; margin-top: 2px;'>
        <span style='font-size: 20px; font-weight: bold; color: #1f77b4;'>📅 Week {week_num}{month_phase_tag}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # 🔹 T+2 在途應收付追蹤器（移到 Week x 下面）
    with st.expander("💰 T+2 在途應收付", expanded=False):
        render_t2_settlement_tracker()

    # 🔹 T+2 下方提示文字
    st.markdown(
        """
        <div style='text-align: center; font-size: 18px; font-weight: 500; margin-top: -6px; margin-bottom: 12px; line-height: 1.2; padding: 0;'>
            <span style='color: #ff4b4b; font-family: "DFKai-SB", "KaiTi", "STKaiti", "Segoe Script", "Comic Sans MS", cursive; font-size: 20px; font-weight: 550; text-decoration: underline;'>波段看趨勢</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 🔹 左側底部提示文字（藍圈位置）
    st.markdown(
        """
        <div style='text-align: center; font-size: 18px; font-weight: 500; margin-top: -6px; margin-bottom: 12px; line-height: 1.30; padding: 0;'>
            <div style='margin: 0;'>
                𝓟𝓻𝓸 <span style='color: #1f77b4; font-family: "DFKai-SB", "KaiTi", "STKaiti", "Segoe Script", "Comic Sans MS", cursive; font-size: 20px; font-weight: 550;'>沒事就「續抱」</span>
            </div>
            <div style='margin-top: 6px;'>
                <span style='color: #1f77b4; font-family: "DFKai-SB", "KaiTi", "STKaiti", "Segoe Script", "Comic Sans MS", cursive; font-size: 19px; font-weight: 500;'>「關K低 三盤沒破」or</span>
            </div>
            <div style='margin-top: 6px;'>
                <span style='color: #1f77b4; font-family: "DFKai-SB", "KaiTi", "STKaiti", "Segoe Script", "Comic Sans MS", cursive; font-size: 17px; font-weight: 500;'>守住「基準 扣抵 5日均」</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 🔹 移到左側最底部：temp_list 快速檢視
    render_temp_list_expander(
        temp_txt="temp_list.txt",
        db_path="data/institution.db",
        title="📄 show temp_list"
    )

with col2:
    if selected:
        with st.expander("🧮 RSI / RS & 乖離率 / 成交量 / PEG 快算 / 📕 第一根帶量突破k棒可上車 / 🎢 買在 三盤突破(遠離上方壓力 or 帶量突破壓力) or 上升波.量縮拉回支撐 / 🥀 賣在力竭 / ☄️ 量即↗↘", expanded=False):
            col_left, col_mid, col_right = st.columns([2, 3, 3])
            with col_left:
                display_rs_rsi_info(selected)

            with col_mid:
                render_bias_calculator(key_suffix=selected, compact=True)
                render_volume_avg_calculator(key_suffix=selected, compact=True, default_days=5)

            with col_right:
                render_peg_calculator(selected, sdk=sdk, key_suffix=selected)

        result = display_price_break_analysis(selected, dl=dl, sdk=sdk)
        if result:
            today_date, c1, o, c2, h, l, w1, w2, m1, m2, summary_term1, summary_term2, summary_term3 = result
        else:
            # 如果沒有結果，設定預設值避免後續錯誤
            today_date = c1 = o = c2 = h = l = w1 = w2 = m1 = m2 = None
        
        # 只有在有結果時才顯示區間視覺化
        if result:
            st.subheader("📌 接近高點(有機會過高，但高點本身也是壓力)、過高(強勢股)")
            fig_zone = plot_price_position_zone(stock_display_reversed, today_date, c1, o, c2, h, l, w1, w2, m1, m2)
            st.plotly_chart(fig_zone, use_container_width=True)
        
        st.markdown(f"""
        <span style='font-size:20px'>📈 強勢股，應在上漲過程中，守住基準價與扣抵值(上軌道 可續抱) 與5日均</span>
        <span style='font-size:16px; color:gray'>　{selected_display}</span>
        """, unsafe_allow_html=True)
        fig_strength = analyze_10day_strength(selected)
        st.plotly_chart(fig_strength, use_container_width=True, config={"displayModeBar": False})

        st.subheader("📉 收盤價 (日)")
        fig_price = plot_price_interactive(selected)
        st.plotly_chart(fig_price, use_container_width=True)
        

        st.subheader("📈 主力 買賣超 & 買賣家數差 (日)")
        
        # 🔹 添加更新按鈕（與訊息在同一行）
        col_title, col_btn, col_msg = st.columns([3, 1, 4])
        
        with col_btn:
            if st.button("🔄 更新", key=f"update_main_force_{selected}", help="背景更新此股票的主力買賣超資料"):
                trigger_main_force_update(selected)
        
        with col_msg:
            # 顯示背景執行提示（3秒後自動淡出）
            if st.session_state.get(f'show_update_msg_{selected}', False):
                st.markdown("""
                <div id="update-msg" style="
                    padding: 0.5rem 1rem;
                    background-color: #d1ecf1;
                    border: 1px solid #bee5eb;
                    border-radius: 0.25rem;
                    color: #0c5460;
                    animation: fadeOut 0.5s ease-in-out 2.5s forwards;
                ">
                    ℹ️ ⏳ 背景更新中...完成後會有提示音
                </div>
                <style>
                    @keyframes fadeOut {
                        from { opacity: 1; }
                        to { opacity: 0; visibility: hidden; }
                    }
                </style>
                <script>
                    setTimeout(function() {
                        var msg = document.getElementById('update-msg');
                        if (msg) {
                            setTimeout(function() {
                                msg.style.display = 'none';
                            }, 3000);
                        }
                    }, 100);
                </script>
                """, unsafe_allow_html=True)
                # 重置狀態（避免訊息一直顯示）
                st.session_state[f'show_update_msg_{selected}'] = False
        
        fig_main1, fig_main2 = plot_main_force_charts(selected)
        st.plotly_chart(fig_main1, use_container_width=True)
        st.plotly_chart(fig_main2, use_container_width=True)
        

        st.subheader("📊 外資、投信 買賣超 & 持股比率 (日)")
        
        # 🔹 添加更新按鈕（與訊息在同一行）
        col_title2, col_btn2, col_msg2 = st.columns([3, 1, 4])
        
        with col_btn2:
            if st.button("🔄 更新", key=f"update_institutional_{selected}", help="背景更新此股票的外資、投信買賣超與持股比率資料"):
                trigger_institutional_update(selected)
        
        with col_msg2:
            # 顯示背景執行提示（3秒後自動淡出）
            if st.session_state.get(f'show_update_msg_inst_{selected}', False):
                st.markdown("""
                <div id="update-msg-inst" style="
                    padding: 0.5rem 1rem;
                    background-color: #d1ecf1;
                    border: 1px solid #bee5eb;
                    border-radius: 0.25rem;
                    color: #0c5460;
                    animation: fadeOut 0.5s ease-in-out 2.5s forwards;
                ">
                    ℹ️ ⏳ 背景更新中...完成後會有提示音
                </div>
                <style>
                    @keyframes fadeOut {
                        from { opacity: 1; }
                        to { opacity: 0; visibility: hidden; }
                    }
                </style>
                <script>
                    setTimeout(function() {
                        var msg = document.getElementById('update-msg-inst');
                        if (msg) {
                            setTimeout(function() {
                                msg.style.display = 'none';
                            }, 3000);
                        }
                    }, 100);
                </script>
                """, unsafe_allow_html=True)
                # 重置狀態（避免訊息一直顯示）
                st.session_state[f'show_update_msg_inst_{selected}'] = False
        
        fig1, fig2 = plot_institution_combo_plotly(selected)
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)


        st.subheader("📈 籌碼集中度 & 千張大戶持股比率 (週)")
        fig3, fig4 = plot_holder_concentration_plotly(selected)
        st.plotly_chart(fig3, use_container_width=True)
        st.plotly_chart(fig4, use_container_width=True)
        
        st.subheader("📈 營收年增率 & 月營收 & 營收月增率")
        fig5, fig6, fig7, df_revenue = plot_monthly_revenue_plotly(selected)
        st.plotly_chart(fig5, use_container_width=True)
        
        # 🔹 營收 YoY 條件提示
        if df_revenue is not None and not df_revenue.empty:
            # 取得最近兩個月的 YoY（df 已經按 year_month 排序）
            latest_yoy = df_revenue.iloc[-1]["yoy_rate"] if len(df_revenue) >= 1 else None
            second_latest_yoy = df_revenue.iloc[-2]["yoy_rate"] if len(df_revenue) >= 2 else None
            
            alerts = []
            
            # 條件1: 最近連續兩個月 YoY > 20%
            if latest_yoy is not None and second_latest_yoy is not None:
                if latest_yoy > 20 and second_latest_yoy > 20:
                    alerts.append(f"🔥 **連續兩個月 YoY > 20%** ({second_latest_yoy:.1f}% → {latest_yoy:.1f}%)")
            
            # 條件2: 最近單月 YoY > 30%
            if latest_yoy is not None and latest_yoy > 30:
                alerts.append(f"⚡ **最新單月 YoY > 30%** ({latest_yoy:.1f}%)")
            
            # 顯示提示
            if alerts:
                st.success("📊 **營收成長強勁提示：**\n" + "\n".join([f"- {alert}" for alert in alerts]))
        
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


with st.expander("📘 說明：這是什麼？"):
    st.markdown("""
    - **📈 多頭大賺小賠邏輯: 上不預設高點，下停損/利 設好**            
    - **📈 做波段主要是看趨勢，單一k棒的漲跌一般不會改變趨勢**
    - **📈 價漲「量增」，是主力願意追價買進的結果，說明後面看更多; 📉 價跌「量增」，是主力願意降價求售的結果，說明後面看更空**
    - **📈 價漲「量增」，主力看多做多，趨勢向上; 📉 價跌「量增」，主力看空做空，趨勢向下**
    - **📈 上漲過程中，只要「帶量大紅k低點沒跌破」、「三盤沒跌破」，行情都能延續，應續抱**
    - **📈 進場 either 遠離(上方)壓力 or 突破壓力; 趨勢向上，可以考慮在量縮拉回 下有支撐時進場**
    - **🚩 第1根5分K低點 ✚ 盤中均價線 不能破**
    - **🎯 預判 蹲點 找飆股:** 技術線型(找已吃貨且還沒噴的) & 籌碼(主力守與拉的動機) & 扣抵(適合進攻的地形)
    - 工作流程: 紅字加碼/鎖利-> 分析匯集精選股-> 高分贏勢股 + 其他股
    - 股票代碼清單來自 `my_stock_holdings.txt`
    - 自動更新資料至 `institution.db`
    - **向上趨勢盤:** (1) 現價 過週高與月高  (2) 5_10_24均線上彎且多頭排列  (3) 現價站上5日均; 向下趨勢盤 (4) 現價站上上彎5週均線: 反向推論
    - **扣抵向下，唯一不能出現的情況是價跌量增(面對壓力變小還被賣下去，代表賣壓很重，就不該碰)**; 扣抵向上，強勢股應盡快帶量向上攻擊，脫離扣抵值
    - **乖離率健康範圍:** 5日(0-1✅ 1-2✔️ >10⚠️) / 10日(0-2✅ 2-4✔️ >20⚠️) / 24日(0-4✅ 4-8✔️ >40⚠️) / 開口(0-1.8✅ 1.8-3.6✔️ >20⚠️)
    - 圖表類型包含：
        - RS / RSI 評分 (RS>90 強勢股、RSI>70 超買 RSI<30 超賣)(每晚的10:50 更新最新排名)
        - 每日收盤價
        - 外資 / 投信 買賣超與持股比率 (日)
        - 主力買賣超與買賣家數差 (日)       
        - 籌碼集中度與大戶比率 (週)
        - 月營收與年增率 (月)
        - 三率（毛利率、營業利益率、稅後淨利率）與季收盤價 (季)        
    """)