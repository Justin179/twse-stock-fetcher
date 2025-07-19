import streamlit as st
from analyze.analyze_price_break_conditions_dataloader import (
    analyze_stock, get_today_prices, get_recent_prices,
    get_yesterday_hl, get_week_month_high_low
)

def display_price_break_analysis(stock_id: str):
    try:
        today = get_today_prices(stock_id)
        today_date = today["date"]
        db_data = get_recent_prices(stock_id, today_date)
        w1, w2, m1, m2 = get_week_month_high_low(stock_id)
        h, l = get_yesterday_hl(stock_id, today_date)
        c1, o, c2 = today["c1"], today["o"], today["c2"]
        v1 = db_data.iloc[0]["volume"] if len(db_data) > 0 else None
        tips = analyze_stock(stock_id)

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown(f"- **昨日成交量**：{v1 / 1000:,.0f} 張" if v1 is not None else "- **昨日成交量**：無資料")
            st.markdown(f"- **昨日收盤價**：{c2}")
            st.markdown(f"- **今日開盤價**：{o}")
            st.markdown(f"- **今日收盤價(現價)**：<span style='color:blue; font-weight:bold; font-size:18px'>{c1}</span>", unsafe_allow_html=True)

        with col_right:
            st.markdown("**提示訊息：**")
            for tip in tips:
                if ("過" in tip and "高" in tip) or ("開高" in tip):
                    icon = "✅"
                elif ("破" in tip and "低" in tip) or ("開低" in tip):
                    icon = "❌"
                elif "開平" in tip:
                    icon = "➖"
                else:
                    icon = "ℹ️"

                tip_html = f'<span style="color:blue">{tip}</span>' if tip.startswith("今收盤(現價)") else tip
                st.markdown(f"{icon} {tip_html}", unsafe_allow_html=True)

        return c1, o, c2, h, l, w1, w2, m1, m2

    except Exception as e:
        st.warning(f"⚠️ 無法取得關鍵價位分析資料：{e}")
        return None
