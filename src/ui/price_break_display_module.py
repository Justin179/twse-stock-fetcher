import streamlit as st
from analyze.analyze_price_break_conditions_dataloader import (
    analyze_stock, get_today_prices, get_recent_prices,
    get_yesterday_hl, get_week_month_high_low
)

import sqlite3
import pandas as pd
from datetime import datetime

def is_price_above_upward_wma5(stock_id: str, today_date: str, today_close: float) -> bool:
    """
    判斷本週收盤價是否站上上彎的5週均線。

    條件1：今日收盤價 > 本週 WMA5
    條件2：本週 WMA5 > 前5週收盤價（代表上彎）
    """
    conn = sqlite3.connect("data/institution.db")
    df = pd.read_sql_query(
        "SELECT date, close FROM twse_prices WHERE stock_id = ? ORDER BY date",
        conn, params=(stock_id,)
    )
    conn.close()

    if df.empty:
        return False

    df["date"] = pd.to_datetime(df["date"])
    df["year_week"] = df["date"].apply(lambda d: f"{d.isocalendar().year}-{d.isocalendar().week:02d}")
    last_trading_per_week = df.groupby("year_week").tail(1).copy() # 取得每一週「最後一個交易日」
    last_trading_per_week = last_trading_per_week.sort_values("date")

    # 找到本週 week key (使用 isocalendar() 取得 今年是第幾週: 2025-30)
    target_date = pd.to_datetime(today_date)
    this_week_key = f"{target_date.isocalendar().year}-{target_date.isocalendar().week:02d}"

    # 找出本週在列表中的 index
    if this_week_key not in last_trading_per_week["year_week"].values:
        return False
    # 找出本週在這個資料表中的位置（定錨位置）
    idx = last_trading_per_week[last_trading_per_week["year_week"] == this_week_key].index[0]
    pos = last_trading_per_week.index.get_loc(idx)

    if pos < 4:
        return False  # 不足 5 週資料

    wma5_df = last_trading_per_week.iloc[pos-4:pos+1].copy() # 取得本週 + 前4週的資料（共5週）
    wma5_df.iloc[-1, wma5_df.columns.get_loc("close")] = today_close  # ⬅️ 替換本週收盤價為 today["c1"]
    wma5 = wma5_df["close"].mean() # 算出5週平均
    close_5_weeks_ago = last_trading_per_week.iloc[pos - 5]["close"]

    cond1 = today_close > wma5 # 站上5週均線
    cond2 = today_close > close_5_weeks_ago # 5週均線上彎

    return cond1 and cond2 # 站上上彎的5週均線


def display_price_break_analysis(stock_id: str, dl=None, sdk=None):
    try:
        today = get_today_prices(stock_id, sdk)
        # print(f"🔍 取得今日價格資料：{today}")
        today_date = today["date"]
        db_data = get_recent_prices(stock_id, today_date)
        w1, w2, m1, m2 = get_week_month_high_low(stock_id)
        h, l = get_yesterday_hl(stock_id, today_date)
        c1, o, c2 = today["c1"], today["o"], today["c2"]
        v1 = db_data.iloc[0]["volume"] if len(db_data) > 0 else None
        above_upward_wma5 = is_price_above_upward_wma5(stock_id, today_date, c1)

        tips = analyze_stock(stock_id, dl=dl, sdk=sdk)

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown(f"- **昨日成交量**：{v1 / 1000:,.0f} 張" if v1 is not None else "- **昨日成交量**：無資料")
            st.markdown(f"- **昨日收盤價**：{c2}")
            st.markdown(f"- **今日({today_date[5:]})開盤價**：{o}")
            st.markdown(f"- **今日({today_date[5:]})收盤價(現價)**：<span style='color:blue; font-weight:bold; font-size:18px'>{c1}</span>", unsafe_allow_html=True)
            if above_upward_wma5:
                st.markdown("- ✅ **現價站上 上彎5週均線！**", unsafe_allow_html=True)
            else:
                st.markdown("- ❌ **現價未站上 上彎5週均線**", unsafe_allow_html=True)

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

        return today_date, c1, o, c2, h, l, w1, w2, m1, m2

    except Exception as e:
        st.warning(f"⚠️ 無法取得關鍵價位分析資料：{e}")
        return None
