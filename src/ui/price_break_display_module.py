import streamlit as st
from analyze.analyze_price_break_conditions_dataloader import (
    analyze_stock, get_today_prices, get_recent_prices,
    get_yesterday_hl, get_week_month_high_low
)
from common.db_helpers import fetch_close_history_from_db, fetch_close_history_trading_only_from_db
from analyze.price_baseline_checker import check_price_vs_baseline_and_deduction
from analyze.moving_average_weekly import is_price_above_upward_wma5
from analyze.moving_average_monthly import is_price_above_upward_mma5
# 檔頭適當位置加入
from analyze.week_month_kbar_tags_helper import get_week_month_tags


import sqlite3
import pandas as pd
from datetime import datetime

from ui.bias_calculator import render_bias_calculator
import re
from math import isclose
from typing import Optional

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

def is_uptrending_now(stock_id: str, today_date: str, c1, w1, m1, ma5, ma10, ma24, tol: float = 1e-6) -> bool:
    """
    判斷「當下現價 c1」是否為【向上趨勢盤】：
      條件1：c1 > w1 且 c1 > m1
      條件2：上彎5日均 > 上彎10日均 > 上彎24日均，且三條均線皆為上彎
             （上彎沿用現有定義：c1 > N日均線的「基準價 baseline」）
      條件3：c1 > 5日均線（且 5日均線必為上彎；由條件2中的 up5 保證）
    其餘則視為【盤整盤】（False）。
    """
    # 基本數據不足
    if any(x is None for x in [c1, w1, m1, ma5, ma10, ma24]):
        return False

    try:
        c1 = float(c1); w1 = float(w1); m1 = float(m1)
        ma5 = float(ma5); ma10 = float(ma10); ma24 = float(ma24)
    except Exception:
        return False

    # 條件1：現價同時過上週與上月高
    cond1 = (c1 > w1) and (c1 > m1)

    # 取各 N 日均線的「基準價 baseline」
    b5, _  = get_baseline_and_deduction(stock_id, today_date, n=5)
    b10, _ = get_baseline_and_deduction(stock_id, today_date, n=10)
    b24, _ = get_baseline_and_deduction(stock_id, today_date, n=24)
    if any(b is None for b in [b5, b10, b24]):
        return False

    # 均線是否上彎（以 c1 相對 baseline 判斷）
    up5  = c1 > float(b5)  + tol
    up10 = c1 > float(b10) + tol
    up24 = c1 > float(b24) + tol

    # 多頭排列：5 > 10 > 24
    bull_stack = (ma5 > ma10 > ma24)

    # 條件2：三條均線上彎 + 多頭排列
    cond2 = up5 and up10 and up24 and bull_stack

    # 條件3：現價站上 5 日均線
    cond3 = c1 > ma5

    return bool(cond1 and cond2 and cond3)

def is_downtrending_now(
    stock_id: str, today_date: str, c1, w2, m2, ma5, ma10, ma24, tol: float = 1e-6
) -> bool:
    """
    判斷「當下現價 c1」是否為【向下趨勢盤】：
      條件1：c1 < w2 且 c1 < m2
      條件2：下彎5日均 < 下彎10日均 < 下彎24日均，且三條均線皆為下彎
             （下彎定義：c1 < N日均線的「基準價 baseline」）
      條件3：c1 < 5日均線（且 5日均線必為下彎；由條件2中的 down5 保證）
    其餘則視為非向下趨勢（False）。
    """
    if any(x is None for x in [c1, w2, m2, ma5, ma10, ma24]):
        return False

    try:
        c1 = float(c1); w2 = float(w2); m2 = float(m2)
        ma5 = float(ma5); ma10 = float(ma10); ma24 = float(ma24)
    except Exception:
        return False

    # 條件1：現價同時跌破上週低、上月低
    cond1 = (c1 < w2) and (c1 < m2)

    # 取各 N 日均線 baseline
    b5, _  = get_baseline_and_deduction(stock_id, today_date, n=5)
    b10, _ = get_baseline_and_deduction(stock_id, today_date, n=10)
    b24, _ = get_baseline_and_deduction(stock_id, today_date, n=24)
    if any(b is None for b in [b5, b10, b24]):
        return False

    # 是否「下彎」：c1 低於 baseline
    down5  = c1 < float(b5)  - tol
    down10 = c1 < float(b10) - tol
    down24 = c1 < float(b24) - tol

    # 空頭排列：5 < 10 < 24
    bear_stack = (ma5 < ma10 < ma24)

    # 條件2：三條均線皆下彎 + 空頭排列
    cond2 = down5 and down10 and down24 and bear_stack

    # 條件3：現價跌破 5 日均線
    cond3 = c1 < ma5

    return bool(cond1 and cond2 and cond3)




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

# 只標記「(大)漲/(大)跌」與「帶大量」三個關鍵詞的樣式
def _stylize_week_month_tag(line: str) -> str:
    import re
    def repl(m):
        w = m.group(0)
        if w in ("大漲", "漲"):
            return f"<span style='color:#ef4444'>{w}</span>"
        else:  # 大跌 / 跌
            return f"<span style='color:#16a34a'>{w}</span>"
    s = re.sub(r"大漲|大跌|漲|跌", repl, line)
    s = s.replace("帶大量", "<b>帶大量</b>")
    return s



def _safe_float(v) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None

def format_daily_volume_line(today_info: dict, y_volume_in_shares: Optional[float]) -> str:
    """
    回傳一條已排版好的文字，用於顯示：
       今日/昨日成交量：ooo / xxx（達成率：YY%）（富邦api）
    - today_info.get('v') 單位：張
    - y_volume_in_shares  單位：股（DB 取出的 yesterday volume）→ 會自動轉張
    - 若今日或昨日任一缺資料，達成率顯示為 '--'
    - 任何例外都不會丟出，最終回傳一條可安全顯示的字串
    """
    # 今日
    today_v = None
    if isinstance(today_info, dict):
        today_v = _safe_float(today_info.get("v"))

    # 昨日（DB 是「股」→ 轉「張」）
    y_vol = None
    if y_volume_in_shares is not None:
        y_vol = _safe_float(y_volume_in_shares)
        if y_vol is not None:
            y_vol = y_vol / 1000.0

    # 顯示文字
    today_str = f"{today_v:,.0f} 張" if today_v is not None else "查無資料"
    yest_str  = f"{y_vol:,.0f} 張"  if y_vol  is not None else "查無資料"

    # 達成率
    if (today_v is not None) and (y_vol is not None) and (y_vol > 0):
        rate_pct = today_v / y_vol * 100.0
        rate_str = f"{rate_pct:.0f}%"
    else:
        rate_str = "--"

    return f"今/昨 成交量：{today_str} / {yest_str}（達成: {rate_str}, 富邦api）"


def display_price_break_analysis(stock_id: str, dl=None, sdk=None):
    try:
        today = get_today_prices(stock_id, sdk)
        # print(f"📊 {stock_id} 成交量v: {today.get('v')}") # 1101 成交量v: None
        # 盤中 會有成交量 v，這意味著可以算現在的成交量達成率
        # 1101 成交量v: 16991
        # 2330 成交量v: 13800
        
        today_date = today["date"]
        db_data = get_recent_prices(stock_id, today_date)
        w1, w2, m1, m2 = get_week_month_high_low(stock_id)
        h, l = get_yesterday_hl(stock_id, today_date)
        c1, o, c2 = today["c1"], today["o"], today["c2"]
        v1 = db_data.iloc[0]["volume"] if len(db_data) > 0 else None
        
        above_upward_wma5 = is_price_above_upward_wma5(stock_id, today_date, c1, debug_print=False)
        above_upward_mma5 = is_price_above_upward_mma5(stock_id, today_date, c1, debug_print=False)


        tips = analyze_stock(stock_id, dl=dl, sdk=sdk)

        # 取得基準價、扣抵值
        baseline5, deduction5 = get_baseline_and_deduction(stock_id, today_date)
        # 後面 col_mid / col_right 都可用
        ma5  = compute_ma_with_today(stock_id, today_date, c1, 5)
        ma10 = compute_ma_with_today(stock_id, today_date, c1, 10)
        ma24 = compute_ma_with_today(stock_id, today_date, c1, 24)

        col_left, col_mid, col_right = st.columns([3, 2, 2])

        with col_left:
            st.markdown(f"- {format_daily_volume_line(today, v1)}")
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
            # ✅ 在這裡判斷，先把詞條加到 tips
            is_up   = is_uptrending_now(stock_id, today_date, c1, w1, m1, ma5, ma10, ma24)
            is_down = is_downtrending_now(stock_id, today_date, c1, w2, m2, ma5, ma10, ma24)

            if is_up:
                tips.insert(0, "向上趨勢盤，帶量 考慮追價!")
            elif is_down:
                tips.insert(0, "向下趨勢盤，帶量 考慮離場!")
            else:
                tips.insert(0, "非趨勢盤，量縮 考慮區間佈局!")

            # 在 with col_mid:、st.markdown("**提示訊息：**") 之後、for tip in tips: 之前插入
            tags = get_week_month_tags(
                stock_id,
                db_path="data/institution.db",
                today_info=today,                # 直接把今天盤中 dict 傳入（上面已經拿到 today）
                weekly_threshold_pct=6.5,
                monthly_threshold_pct=15.0,
                multiple_ma=1.7,
                multiple_prev=1.5,
                no_shrink_ratio=0.8,
            )

            for idx, tip in enumerate(tips):
                if (tip.startswith("今收盤(現價) 過昨高")
                    or tip.startswith("今收盤(現價) 過上週高點")
                    or tip.startswith("今收盤(現價) 過上月高點")
                    or tip.startswith("向上趨勢盤")):
                    icon = "✅"
                elif ("過" in tip and "高" in tip) or ("開高" in tip):
                    icon = "✔️"
                elif ("破" in tip and "低" in tip) or ("開低" in tip) or (tip.startswith("向下趨勢盤")):
                    icon = "❌"
                elif ("開平" in tip) or (tip.startswith("非趨勢盤")):
                    icon = "➖"
                else:
                    icon = "ℹ️"

                # 原有顏色規則
                if tip.startswith("今收盤(現價)"):
                    tip_html = f'<span style="color:blue">{tip}</span>'
                elif tip.startswith("昨收盤"):
                    tip_html = f'<span style="color:orange">{tip}</span>'
                else:
                    tip_html = tip

                # 先印第 idx 條 tip
                st.markdown(f"{icon} {tip_html}", unsafe_allow_html=True)

                # ⭐ 只在「趨勢盤」這一行印完後，馬上加上上週／上月詞條
                if idx == 0:
                    wk_html = _stylize_week_month_tag(tags['week'])
                    mo_html = _stylize_week_month_tag(tags['month'])
                    # 以縮排箭頭表示附屬於趨勢盤
                    st.markdown(f"　 {wk_html}", unsafe_allow_html=True)
                    st.markdown(f"　 {mo_html}", unsafe_allow_html=True)


        with col_right:
            st.markdown("**乖離率：**")

            render_bias_line("5日均線乖離",  ma5,  c1, stock_id=stock_id, today_date=today_date)
            render_bias_line("10日均線乖離", ma10, c1, stock_id=stock_id, today_date=today_date)
            render_bias_line("24日均線乖離", ma24, c1, stock_id=stock_id, today_date=today_date)
            render_bias_line("10 → 5 均線開口",  ma10, ma5)    # 開口不需判斷彎向
            render_bias_line("24 → 10 均線開口", ma24, ma10)  # 開口不需判斷彎向


        return today_date, c1, o, c2, h, l, w1, w2, m1, m2

    except Exception as e:
        st.warning(f"⚠️ 無法取得關鍵價位分析資料：{e}")
        return None
