import streamlit as st
from analyze.analyze_price_break_conditions_dataloader import (
    analyze_stock, get_today_prices, get_recent_prices,
    get_yesterday_hl, get_week_month_high_low
)
from common.db_helpers import fetch_close_history_from_db, fetch_close_history_trading_only_from_db
from analyze.price_baseline_checker import check_price_vs_baseline_and_deduction


import sqlite3
import pandas as pd
from datetime import datetime

from ui.bias_calculator import render_bias_calculator



def is_price_above_upward_wma5(stock_id: str, today_date: str, today_close: float) -> bool:
    """
    判斷本週收盤價是否站上上彎的5週均線。

    本週：以 today_date 為定錨
    - 如果 today_date 所在 week 尚未出現在 DB，就人工補入本週資料（today_close）
    """
    df = fetch_close_history_from_db(stock_id)
    if df.empty:
        return False

    df["date"] = pd.to_datetime(df["date"])
    df["year_week"] = df["date"].apply(lambda d: f"{d.isocalendar().year}-{d.isocalendar().week:02d}")
    last_trading_per_week = df.groupby("year_week").tail(1).copy()
    last_trading_per_week = last_trading_per_week.sort_values("date")

    # 本週 key（今天的 week）
    target_date = pd.to_datetime(today_date)
    this_week_key = f"{target_date.isocalendar().year}-{target_date.isocalendar().week:02d}"

    # 如果本週不存在，就人工補入
    if this_week_key not in last_trading_per_week["year_week"].values:
        # print(f"⚠️ 本週 {this_week_key} 不存在於 DB，將人工補入 today_close 作為本週收盤價")
        fake_row = {
            "date": today_date,
            "close": today_close,
            "year_week": this_week_key
        }
        last_trading_per_week = pd.concat([last_trading_per_week, pd.DataFrame([fake_row])], ignore_index=True)
        last_trading_per_week = last_trading_per_week.sort_values("year_week")

    # 找到本週在列表中的位置
    idx = last_trading_per_week[last_trading_per_week["year_week"] == this_week_key].index[0]
    pos = last_trading_per_week.index.get_loc(idx)

    if pos < 4:
        print("⚠️ 資料不足無法計算 5 週均線")
        return False

    # 取得本週 + 前4週的資料，並用 today_close 替換本週
    wma5_df = last_trading_per_week.iloc[pos-4:pos+1].copy()
    wma5_df.iloc[-1, wma5_df.columns.get_loc("close")] = today_close

    wma5 = wma5_df["close"].mean()
    close_5_weeks_ago = last_trading_per_week.iloc[pos - 5]["close"]

    cond1 = today_close > wma5 # 站上5週均線
    cond2 = today_close > close_5_weeks_ago # 5週均線上彎
    # print(f"🔍 {stock_id} 今日收盤價: {today_close}, 5週均線: {wma5}, 5週前收盤價: {close_5_weeks_ago}")

    return cond1 and cond2

def get_baseline_and_deduction(stock_id: str, today_date: str):
    """
    基準價：今天往前第 5 個『交易日』的收盤價 => iloc[-6]
    扣抵值：今天往前第 4 個『交易日』的收盤價 => iloc[-5]
    ※『交易日』已排除 close=0 / 無收盤價的日期。
    """
    df = fetch_close_history_trading_only_from_db(stock_id)  # 只取有收盤價的日子
    if df.empty:
        return None, None

    df["date"] = pd.to_datetime(df["date"])
    cutoff = pd.to_datetime(today_date)
    # 僅使用 today_date（含）之前的資料；若 today 尚未入庫，則用 <= today 的最近一筆當「第0天」
    df = df[df["date"] <= cutoff].sort_values("date")

    # 需要「第0天 + 往前至少5天」=> 至少 6 筆
    if len(df) < 6:
        return None, None

    baseline = df.iloc[-6]["close"]   # 前5交易日
    deduction = df.iloc[-5]["close"]  # 前4交易日
    return float(baseline), float(deduction)


def display_price_break_analysis(stock_id: str, dl=None, sdk=None):
    try:
        today = get_today_prices(stock_id, sdk)
        
        today_date = today["date"]
        db_data = get_recent_prices(stock_id, today_date)
        w1, w2, m1, m2 = get_week_month_high_low(stock_id)
        h, l = get_yesterday_hl(stock_id, today_date)
        c1, o, c2 = today["c1"], today["o"], today["c2"]
        v1 = db_data.iloc[0]["volume"] if len(db_data) > 0 else None
        
        above_upward_wma5 = is_price_above_upward_wma5(stock_id, today_date, c1)

        tips = analyze_stock(stock_id, dl=dl, sdk=sdk)

        # 取得基準價、扣抵值
        baseline, deduction = get_baseline_and_deduction(stock_id, today_date)

        col_left, col_mid, col_right = st.columns([4, 3, 2])


        with col_left:
            st.markdown(f"- **昨日成交量**：{v1 / 1000:,.0f} 張" if v1 is not None else "- **昨日成交量**：無資料")
            st.markdown(f'- <span style="color:orange">昨日收盤價：<b>{c2}</b></span>', unsafe_allow_html=True)
            st.markdown(f"- **今日(<span style='color:red'>{today_date[5:]}</span>)開盤價**：{o}", unsafe_allow_html=True)
            st.markdown(f"- **今日(<span style='color:red'>{today_date[5:]}</span>)收盤價(現價)**：<span style='color:blue; font-weight:bold; font-size:18px'>{c1}</span>", unsafe_allow_html=True)
            if above_upward_wma5:
                st.markdown("- ✅ **現價站上 上彎5週均線！**", unsafe_allow_html=True)
            else:
                st.markdown("- ❌ **現價未站上 上彎5週均線**", unsafe_allow_html=True)

            if baseline is not None and deduction is not None:
                msg = check_price_vs_baseline_and_deduction(c1, baseline, deduction)
                st.markdown(msg, unsafe_allow_html=True)
            else:
                st.markdown("- **基準價 / 扣抵值**：資料不足")


        with col_mid:
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

                # 顏色判斷區：今收盤(現價)=藍色，昨收盤=橘色，其餘正常
                if tip.startswith("今收盤(現價)"):
                    tip_html = f'<span style="color:blue">{tip}</span>'
                elif tip.startswith("昨收盤"):
                    tip_html = f'<span style="color:orange">{tip}</span>'
                else:
                    tip_html = tip
                st.markdown(f"{icon} {tip_html}", unsafe_allow_html=True)

            with col_right:
                st.markdown("**乖離率：**")
                

        return today_date, c1, o, c2, h, l, w1, w2, m1, m2

    except Exception as e:
        st.warning(f"⚠️ 無法取得關鍵價位分析資料：{e}")
        return None
