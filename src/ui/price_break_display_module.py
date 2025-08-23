import streamlit as st
from analyze.analyze_price_break_conditions_dataloader import (
    analyze_stock, get_today_prices, get_recent_prices,
    get_yesterday_hl, get_week_month_high_low
)
from common.db_helpers import fetch_close_history_from_db, fetch_close_history_trading_only_from_db
from analyze.price_baseline_checker import check_price_vs_baseline_and_deduction
from analyze.moving_average_monthly import is_price_above_upward_mma5



import sqlite3
import pandas as pd
from datetime import datetime

from ui.bias_calculator import render_bias_calculator
import re
from math import isclose


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

def get_baseline_and_deduction(stock_id: str, today_date: str, n: int = 5):
    """
    針對 N 日均線，回傳兩個參考價位（以「交易日」為單位，已排除無收盤價的日子）：

    基準價 / 扣抵值 的「天數定位」需依 today 是否已入庫來決定：
    - 若 today 尚未入庫：以「目前 df 的最新一筆」為第 0 天 ⇒ 基準 = desc 第 N 筆、扣抵 = desc 第 N-1 筆
    - 若 today 已入庫：以「today」為第 0 天           ⇒ 基準 = desc 第 N+1 筆、扣抵 = desc 第 N   筆

    例（N=5）：
      未入庫：基準 = iloc[-5]，扣抵 = iloc[-4]
      已入庫：基準 = iloc[-6]，扣抵 = iloc[-5]

      再進一步簡化邏輯
        today_date未入庫，基準價為df desc的第5筆
        today_date已入庫，基準價為df desc的第6筆
    """
    df = fetch_close_history_trading_only_from_db(stock_id)  # 只取有收盤價的日子
    if df.empty:
        return None, None

    import pandas as pd
    df["date"] = pd.to_datetime(df["date"])
    cutoff = pd.to_datetime(today_date)

    # 僅使用 today_date（含）之前的資料；若 today 尚未入庫，df 的最後一筆就是「第 0 天」
    df = df[df["date"] <= cutoff].sort_values("date")
    if df.empty:
        return None, None

    latest_in_df = df["date"].iloc[-1].normalize()
    today_norm   = cutoff.normalize()

    # 判斷 today 是否已入庫
    today_in_db = (latest_in_df == today_norm)

    if today_in_db:
        # 需要至少 N+1 筆（含 today 在內）
        need = n + 1
        if len(df) < need:
            return None, None
        baseline = df.iloc[-(n + 1)]["close"]  # desc 第 N+1 筆
        deduction = df.iloc[-n]["close"]       # desc 第 N   筆
    else:
        # 需要至少 N 筆（以 df 最新一筆為第 0 天）
        need = n
        if len(df) < need:
            return None, None
        baseline = df.iloc[-n]["close"]        # desc 第 N   筆
        # N=1 時，desc 第 0 筆就是最後一筆
        deduction = df.iloc[-1]["close"] if n == 1 else df.iloc[-(n - 1)]["close"]

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


def render_bias_line(title: str, a, b, *, stock_id: str = None, today_date: str = None):
    """在畫面印出一行乖離率；正值紅、負值綠，並附上 (A→B) 數字。
       若 title 為「N日均線乖離」，會自動判斷該 N 日均線的「上彎/持平/下彎」並加為前綴。"""
    val = calc_bias(a, b)
    if val is None:
        st.markdown(f"- **{title}**：資料不足")
        return
    color = "#ef4444" if val >= 0 else "#16a34a"

    # ===== 新增：均線彎向前綴（只在 *日均線乖離 生效） =====
    slope_prefix = ""
    if stock_id and today_date:
        m = re.search(r"(\d+)日均線乖離", title)
        if m:
            n = int(m.group(1))
            baseline, _ = get_baseline_and_deduction(stock_id, today_date, n=n)
            if baseline is not None:
                # print(f"🔍 {stock_id} {title} 基準價：{baseline}, 當前值：{b}, today_date:{today_date}")
                if b > baseline + 1e-9:
                    slope_prefix = "<span style='color:#ef4444'>上彎</span>"
                elif isclose(float(b), float(baseline), rel_tol=0.0, abs_tol=1e-6):
                    slope_prefix = "持平"
                else:
                    slope_prefix = "<span style='color:#16a34a'>下彎</span>"

    # ===== 既有：圖示前綴（優先權維持不變） =====
    icon_prefix = ""
    if (title == "24日均線乖離" and val > 15) or \
       ("均線開口" in title and val > 10) or \
       (title == "5日均線乖離" and val > 10):
        icon_prefix = "⚠️ "
    elif title == "5日均線乖離":
        if 0 < val < 0.5:
            icon_prefix = "✅ "
        elif 0.5 <= val < 1:
            icon_prefix = "✔️ "
    elif "均線開口" in title and 0 < val < 0.5:
        icon_prefix = "✔️ "

    # ===== 組合顯示的 title（先彎向，再原 title） =====
    display_title = f"{slope_prefix}{title}" if slope_prefix else title

    st.markdown(
        f"{icon_prefix}{display_title}：<span style='color:{color}; font-weight:700'>{val:+.2f}%</span> ",
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
        above_upward_mma5 = is_price_above_upward_mma5(stock_id, today_date, c1, debug_print=True)



        tips = analyze_stock(stock_id, dl=dl, sdk=sdk)

        # 取得基準價、扣抵值
        baseline5, deduction5 = get_baseline_and_deduction(stock_id, today_date)

        col_left, col_mid, col_right = st.columns([3, 2, 2])

        with col_left:
            st.markdown(f"- 昨日成交量：{v1 / 1000:,.0f} 張 (富邦api)" if v1 is not None else "- 昨日成交量：無資料")
            st.markdown(f"- <span style='color:orange'>昨收：<b>{c2}</b></span> -> 今開(<span style='color:red'>{today_date[5:]}</span>)：<b>{o}</b>", unsafe_allow_html=True)
            st.markdown(f"- **今日(<span style='color:red'>{today_date[5:]}</span>)收盤價(現價)**：<span style='color:blue; font-weight:bold; font-size:18px'>{c1}</span>", unsafe_allow_html=True)

            if above_upward_wma5:
                st.markdown("- ✅ **現價站上 上彎5週均線！**", unsafe_allow_html=True)
            else:
                st.markdown("- ❌ **現價未站上 上彎5週均線**", unsafe_allow_html=True)

            if above_upward_mma5:
                st.markdown("- ✅ **現價站上 上彎5個月均線！**", unsafe_allow_html=True)
            else:
                st.markdown("- ❌ **現價未站上 上彎5個月均線**", unsafe_allow_html=True)

            if baseline5 is not None and deduction5 is not None:
                msg = check_price_vs_baseline_and_deduction(c1, baseline5, deduction5)
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
            render_bias_line("5日均線乖離",  ma5,  c1, stock_id=stock_id, today_date=today_date)
            render_bias_line("10日均線乖離", ma10, c1, stock_id=stock_id, today_date=today_date)
            render_bias_line("24日均線乖離", ma24, c1, stock_id=stock_id, today_date=today_date)
            render_bias_line("10 → 5 均線開口",  ma10, ma5)    # 開口不需判斷彎向
            render_bias_line("24 → 10 均線開口", ma24, ma10)  # 開口不需判斷彎向


        return today_date, c1, o, c2, h, l, w1, w2, m1, m2

    except Exception as e:
        st.warning(f"⚠️ 無法取得關鍵價位分析資料：{e}")
        return None
