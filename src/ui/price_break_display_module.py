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

def compute_ma_with_today(stock_id: str, today_date: str, today_close: float, n: int):
    """
    回傳含今日現價 c1 的 N 日均：
    (today_close + 前 N-1 個『交易日』收盤) / N
    若資料不足則回傳 None
    """
    df = fetch_close_history_trading_only_from_db(stock_id)
    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"])
    cutoff = pd.to_datetime(today_date)
    # 僅取「今天之前」的交易日（不含今天，因為今天盤中尚未入庫）
    df = df[df["date"] < cutoff].sort_values("date")

    need = n - 1
    if len(df) < need:
        return None

    # 取最後 (n-1) 筆收盤價，加上 today_close 後平均
    tail = df["close"].iloc[-need:].astype(float)
    ma = (today_close + float(tail.sum())) / n
    return ma

def calc_bias(a, b):
    """依 A→B 計算乖離率 ((B-A)/A*100)。資料不足或 A=0 時回傳 None。"""
    try:
        if a is None or b is None:
            return None
        a = float(a); b = float(b)
        if a == 0:
            return None
        return (b - a) / a * 100.0
    except Exception:
        return None

def render_bias_line(title: str, a, b):
    """在畫面印出一行乖離率；正值紅、負值綠，並附上 (A→B) 數字。"""
    val = calc_bias(a, b)
    if val is None:
        st.markdown(f"- **{title}**：資料不足")
        return
    color = "#ef4444" if val >= 0 else "#16a34a"

    # ⚠️ 警示條件：
    # 1) title == "24日均線乖離" 且 val > 15
    # 2) title 內含 "均線開口" 且 val > 10
    prefix = "⚠️ " if ((title == "24日均線乖離" and val > 15) or ("均線開口" in title and val > 10)) else ""

    st.markdown(
        f"{prefix}{title}：<span style='color:{color}; font-weight:700'>{val:+.2f}%</span> ",
        unsafe_allow_html=True,
    )


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

        col_left, col_mid, col_right = st.columns([3, 2, 2])


        with col_left:
            st.markdown(f"- 昨日成交量：{v1 / 1000:,.0f} 張" if v1 is not None else "- 昨日成交量：無資料")
            st.markdown(f"- <span style='color:orange'>昨收：<b>{c2}</b></span> -> 今開(<span style='color:red'>{today_date[5:]}</span>)：<b>{o}</b>", unsafe_allow_html=True)
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
                if (tip.startswith("今收盤(現價) 過昨高")
                    or tip.startswith("今收盤(現價) 過上週高點")
                    or tip.startswith("今收盤(現價) 過上月高點")):
                    icon = "✅"
                elif ("過" in tip and "高" in tip) or ("開高" in tip):
                    icon = "✔️"
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
            ma5  = compute_ma_with_today(stock_id, today_date, c1, 5)
            ma10 = compute_ma_with_today(stock_id, today_date, c1, 10)
            ma24 = compute_ma_with_today(stock_id, today_date, c1, 24)
            render_bias_line("5日均線乖離", ma5, c1)         # (A=MA5,  B=c1)
            render_bias_line("10日均線乖離", ma10, c1)       # (A=MA10, B=c1)
            render_bias_line("24日均線乖離", ma24, c1)       # (A=MA24, B=c1)
            render_bias_line("10 → 5 均線開口", ma10, ma5)   # (A=MA10, B=MA5)
            render_bias_line("24 → 10 均線開口", ma24, ma10) # (A=MA24, B=MA10)

        return today_date, c1, o, c2, h, l, w1, w2, m1, m2

    except Exception as e:
        st.warning(f"⚠️ 無法取得關鍵價位分析資料：{e}")
        return None
