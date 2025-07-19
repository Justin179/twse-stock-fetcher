import streamlit as st
from fetch.fetch_rs_rsi_info import fetch_rs_rsi_info

def display_rs_rsi_info(stock_id: str):
    """顯示 RSI / RS 概況到 Streamlit 介面"""
    rs_info = fetch_rs_rsi_info(stock_id)
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
