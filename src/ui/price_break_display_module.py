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
from typing import Optional, Dict
from decimal import Decimal, ROUND_HALF_UP

def get_baseline_and_deduction(stock_id: str, today_date: str, n: int = 5):
    """
    針對 N 日均線，回傳：
      baseline, deduction, deduction1, deduction2, deduction3, prev_baseline
    baseline / 扣抵值 的「天數定位」說明同原本：
      - 若 today 尚未入庫：以 df 最新一筆為第 0 天 ⇒ baseline = desc 第 N 筆
      - 若 today 已入庫：以 today 為第 0 天           ⇒ baseline = desc 第 N+1 筆
    並同時嘗試取 baseline 之後的三個交易日作為扣1/扣2/扣3（若不存在則為 None）。
    """
    df = fetch_close_history_trading_only_from_db(stock_id)  # 只取有收盤價的日子
    if df.empty:
        return None, None, None, None, None, None

    import pandas as pd
    df["date"] = pd.to_datetime(df["date"])
    cutoff = pd.to_datetime(today_date)

    # 僅使用 today_date（含）之前的資料；若 today 尚未入庫，df 的最後一筆就是「第 0 天」
    df = df[df["date"] <= cutoff].sort_values("date").reset_index(drop=True)
    if df.empty:
        return None, None, None, None, None, None

    latest_in_df = df["date"].iloc[-1].normalize()
    today_norm   = cutoff.normalize()

    # 判斷 today 是否已入庫
    today_in_db = (latest_in_df == today_norm)

    # 決定 baseline 的 index（以 df 的正向索引 0..len-1 表示）
    if today_in_db:
        # 需要至少 N+1 筆（含 today 在內）
        need = n + 1
        if len(df) < need:
            return None, None, None, None, None, None
        baseline_idx = len(df) - (n + 1)
    else:
        # 需要至少 N 筆（以 df 最新一筆為第 0 天）
        need = n
        if len(df) < need:
            return None, None, None, None, None, None
        baseline_idx = len(df) - n

    def _safe_get_close_at(idx: int):
        if 0 <= idx < len(df):
            try:
                return float(df.iloc[idx]["close"])
            except Exception:
                return None
        return None

    baseline   = _safe_get_close_at(baseline_idx)
    deduction  = _safe_get_close_at(baseline_idx + 1)  # 原本的扣抵值（baseline 的下一個交易日）
    ded_1      = _safe_get_close_at(baseline_idx + 2)  # 扣1
    ded_2      = _safe_get_close_at(baseline_idx + 3)  # 扣2
    ded_3      = _safe_get_close_at(baseline_idx + 4)  # 扣3

    # 新增：baseline 前一交易日收盤（昨基），若不存在則 None
    prev_baseline = _safe_get_close_at(baseline_idx - 1) if baseline_idx is not None else None

    return baseline, deduction, ded_1, ded_2, ded_3, prev_baseline



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

def get_week_month_baseline_and_deduction(stock_id: str, today_date: str, period: str = 'W', n: int = 5):
    """
    計算週K棒或月K棒的 N 均線基準價、扣抵值、前基準
    
    參數:
        stock_id: 股票代碼
        today_date: 今日日期字串 (YYYY-MM-DD)
        period: 'W' 為週K棒, 'M' 為月K棒
        n: 均線週期，預設為 5
    
    回傳:
        (baseline, deduction, prev_baseline) 或 (None, None, None)
    """
    import sqlite3
    from datetime import datetime
    
    if period == 'W':
        # 週K棒：使用 twse_prices_weekly 資料表
        # 直接從資料庫查詢，按時間倒序取得最近的週K資料
        conn = sqlite3.connect('data/institution.db')
        
        # 取得今天的ISO週數（用於判斷是否包含當週）
        today = pd.to_datetime(today_date)
        today_year, today_week, _ = today.isocalendar()
        current_year_week = f"{today_year}-{today_week:02d}"
        
        # 查詢足夠多的週K資料（確保能涵蓋需要的週數）
        # 重要：只查詢 <= 當前週的資料，避免取到未來資料
        cursor = conn.cursor()
        cursor.execute("""
            SELECT year_week, close
            FROM twse_prices_weekly
            WHERE stock_id = ?
            AND year_week <= ?
            ORDER BY year_week DESC
            LIMIT 20
        """, [stock_id, current_year_week])
        
        all_weeks = cursor.fetchall()
        conn.close()
        
        if len(all_weeks) < n + 2:
            return None, None, None
        
        # 轉換為列表 [(year_week, close), ...]，已經是倒序
        # all_weeks[0] 是最新的週K
        
        # 判斷最新週K是否為當週（正在進行中）
        latest_year_week = all_weeks[0][0]
        latest_year, latest_week = map(int, latest_year_week.split('-'))
        
        # 如果最新週K就是當週，則跳過它（因為尚未完成）
        if latest_year == today_year and latest_week == today_week:
            # 當週尚未完成，從 all_weeks[1] 開始算起
            start_idx = 1
        else:
            # 當週已完成或今天不在最新週內
            start_idx = 0
        
        # 從 start_idx 開始往前數 n 根，取得基準/扣抵/前基準
        # 基準週 = start_idx + n - 1 (往前數第 n 根)
        # 扣抵週 = start_idx + n - 2 (往前數第 n-1 根)
        # 前基準週 = start_idx + n (往前數第 n+1 根)
        baseline_idx = start_idx + n - 1
        deduction_idx = start_idx + n - 2
        prev_baseline_idx = start_idx + n
        
        # 確保索引不超出範圍
        if prev_baseline_idx >= len(all_weeks):
            return None, None, None
        
        baseline = all_weeks[baseline_idx][1] if baseline_idx < len(all_weeks) else None
        deduction = all_weeks[deduction_idx][1] if deduction_idx < len(all_weeks) else None
        prev_baseline = all_weeks[prev_baseline_idx][1] if prev_baseline_idx < len(all_weeks) else None
        
        return baseline, deduction, prev_baseline
        
    elif period == 'M':
        # 月K棒：使用 twse_prices_monthly 資料表
        today = pd.to_datetime(today_date)
        year = today.year
        current_month = today.month
        
        # 計算目標月份
        baseline_month = current_month - n      # 基準月 (例: 10 - 5 = 5)
        deduction_month = current_month - (n - 1)  # 扣抵月 (例: 10 - 4 = 6)
        prev_baseline_month = current_month - (n + 1)  # 前基準月 (例: 10 - 6 = 4)
        
        # 處理跨年的情況
        def get_year_month(y, m):
            while m <= 0:
                m += 12
                y -= 1
            while m > 12:
                m -= 12
                y += 1
            return y, m
        
        baseline_y, baseline_m = get_year_month(year, baseline_month)
        deduction_y, deduction_m = get_year_month(year, deduction_month)
        prev_baseline_y, prev_baseline_m = get_year_month(year, prev_baseline_month)
        
        # 查詢資料庫
        conn = sqlite3.connect('data/institution.db')
        query = """
        SELECT year_month, close
        FROM twse_prices_monthly
        WHERE stock_id = ?
        AND year_month IN (?, ?, ?)
        """
        year_months = [
            f"{prev_baseline_y}-{prev_baseline_m:02d}",
            f"{baseline_y}-{baseline_m:02d}",
            f"{deduction_y}-{deduction_m:02d}"
        ]
        
        cursor = conn.cursor()
        cursor.execute(query, [stock_id] + year_months)
        results = cursor.fetchall()
        conn.close()
        
        # 建立對應關係
        month_data = {row[0]: row[1] for row in results}
        
        prev_baseline = month_data.get(f"{prev_baseline_y}-{prev_baseline_m:02d}")
        baseline = month_data.get(f"{baseline_y}-{baseline_m:02d}")
        deduction = month_data.get(f"{deduction_y}-{deduction_m:02d}")
        
        return baseline, deduction, prev_baseline
    
    else:
        return None, None, None

def is_uptrending_now(stock_id: str, today_date: str, c1, w1, m1, ma5, ma10, ma24, above_upward_wma5: bool = False, tol: float = 1e-6) -> bool:
    """
    判斷「當下現價 c1」是否為【向上趨勢盤】：
      條件1：c1 > w1 且 c1 > m1
      條件2：上彎5日均 > 上彎10日均 > 上彎24日均，且三條均線皆為上彎
             （上彎沿用現有定義：c1 > N日均線的「基準價 baseline」）
      條件3：c1 > 5日均線（且 5日均線必為上彎；由條件2中的 up5 保證）
      條件4：現價站上上彎5週均線（above_upward_wma5 == True）
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
    b5, _, * _ = get_baseline_and_deduction(stock_id, today_date, n=5)
    b10, _, * _ = get_baseline_and_deduction(stock_id, today_date, n=10)
    b24, _, * _ = get_baseline_and_deduction(stock_id, today_date, n=24)
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
    
    # 條件4：現價站上上彎5週均線
    cond4 = above_upward_wma5

    return bool(cond1 and cond2 and cond3 and cond4)

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
    b5, _, * _ = get_baseline_and_deduction(stock_id, today_date, n=5)
    b10, _, * _ = get_baseline_and_deduction(stock_id, today_date, n=10)
    b24, _, * _ = get_baseline_and_deduction(stock_id, today_date, n=24)
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
            baseline, * _ = get_baseline_and_deduction(stock_id, today_date, n=n)
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

    # ===== 組合顯示的 title（先彎向，再原 title）=====
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

def _inject_rate_after_volume(raw_line: str, rate: float | None) -> str:
    """
    將「達成率」插入到『帶大量/一般量』之後，並讓『，留上影線』永遠放在該段最後。
    例：
      上週 跌(-0.67%) 帶大量，留上影線  →  上週 跌(-0.67%) 帶大量（達成: 7%），留上影線
      上月 跌(-7.04%) 一般量            →  上月 跌(-7.04%) 一般量（達成: 53%）
    """
    if rate is None:
        return raw_line

    pattern = r"(帶大量|一般量)(，留上影線)?"
    def repl(m: re.Match):
        vol = m.group(1)
        shadow = m.group(2) or ""
        return f"{vol}（達成: <span style='color:#ef4444'>{rate:.0f}%</span>）{shadow}"

    return re.sub(pattern, repl, raw_line, count=1)

def _safe_float(v) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None



def _load_recent_daily_volumes(db_path: str, stock_id: str, last_n: int = 300) -> pd.DataFrame:
    """
    讀取最近 N 日的日K（只要日期與成交量），來源：twse_prices。
    注意：DB 成交量單位為「股」。
    """
    sql = f"""
        SELECT date, volume
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT {int(last_n)}
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(sql, conn, params=[stock_id], parse_dates=["date"])
    df = df.dropna(subset=["date", "volume"]).copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    # 僅保留 >0 的有效成交量
    df = df[df["volume"] > 0].sort_values("date").reset_index(drop=True)
    return df

def _attach_intraday_volume(df: pd.DataFrame, today_info: dict) -> pd.DataFrame:
    """
    把今日盤中資料併進日K序列：
    - today_info['date']：字串日期
    - today_info['v']   ：張（需 *1000 轉股）
    若 df 已含今日，更新其 volume；否則直接 append。
    """
    if not isinstance(today_info, dict) or not today_info.get("date"):
        return df
    t_date = pd.to_datetime(str(today_info["date"])).normalize()
    v = today_info.get("v", None)
    try:
        v = float(v) * 1000.0 if v is not None else None  # 張→股
    except Exception:
        v = None

    if v is None:
        return df

    dfx = df.copy()
    mask = (dfx["date"] == t_date)
    if mask.any():
        dfx.loc[mask, "volume"] = float(v)
    else:
        dfx = pd.concat([dfx, pd.DataFrame([{"date": t_date, "volume": float(v)}])], ignore_index=True)
    return dfx.sort_values("date").reset_index(drop=True)

def _aggregate_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """與互動圖一致：使用 ISO 年-週，volume 為該週總和。"""
    iso = df["date"].dt.isocalendar()
    wk = (
        df.assign(year_week = iso.year.astype(str) + "-" + iso.week.map(lambda x: f"{int(x):02d}"))
          .groupby("year_week", as_index=False)["volume"].sum()
          .rename(columns={"year_week": "key", "volume": "volume_sum"})
          .sort_values("key").reset_index(drop=True)
    )
    return wk

def _aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """與互動圖一致：使用 YYYY-MM，volume 為該月總和。"""
    mk = (
        df.assign(year_month = df["date"].dt.strftime("%Y-%m"))
          .groupby("year_month", as_index=False)["volume"].sum()
          .rename(columns={"year_month": "key", "volume": "volume_sum"})
          .sort_values("key").reset_index(drop=True)
    )
    return mk

def _calc_achievement(curr: float, prev: Optional[float]) -> Optional[float]:
    """計算達成率（curr / prev * 100），若前值缺或<=0 則回傳 None。"""
    try:
        prev = float(prev) if prev is not None else None
        curr = float(curr)
        if (prev is None) or (prev <= 0):
            return None
        return curr / prev * 100.0
    except Exception:
        return None

def compute_week_month_volume_achievement(
    stock_id: str,
    today_info: dict,
    db_path: str = "data/institution.db",
) -> Dict[str, Optional[float]]:
    """
    回傳 {'week': 週量達成率, 'month': 月量達成率}：
      - 以 DB 的日K成交量（股）為基礎，併入今日盤中成交量（張→股）
      - 以 ISO 週 / YYYY-MM 聚合
      - 使用「本週/本月累計」對比「上一週/上一月總量」計算達成率
    """
    df = _load_recent_daily_volumes(db_path, stock_id, last_n=300)
    if df.empty:
        return {"week": None, "month": None}

    # 併入今日盤中
    df2 = _attach_intraday_volume(df, today_info)
    if df2.empty:
        return {"week": None, "month": None}

    # 取今日所屬週/月的 key
    t_date = pd.to_datetime(str(today_info.get("date", df2["date"].iloc[-1]))).normalize()
    iso = t_date.isocalendar()
    curr_wk_key = f"{int(iso.year)}-{int(iso.week):02d}"
    curr_mo_key = t_date.strftime("%Y-%m")

    # 週聚合 & 月聚合
    wk = _aggregate_weekly(df2)
    mo = _aggregate_monthly(df2)

    # 週：找目前週與上一週
    wk_idx = wk.index[wk["key"] == curr_wk_key].tolist()
    week_rate = None
    if wk_idx:
        i = wk_idx[0]
        curr_wk = float(wk.iloc[i]["volume_sum"])
        prev_wk = float(wk.iloc[i-1]["volume_sum"]) if i-1 >= 0 else None
        week_rate = _calc_achievement(curr_wk, prev_wk)

    # 月：找目前月與上一月
    mo_idx = mo.index[mo["key"] == curr_mo_key].tolist()
    month_rate = None
    if mo_idx:
        j = mo_idx[0]
        curr_mo = float(mo.iloc[j]["volume_sum"])
        prev_mo = float(mo.iloc[j-1]["volume_sum"]) if j-1 >= 0 else None
        month_rate = _calc_achievement(curr_mo, prev_mo)

    return {"week": week_rate, "month": month_rate}


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
        rate_str = f"<span style='color:#ef4444'>{rate_pct:.0f}%</span>"
    else:
        rate_str = "--"

    return (
        f"今/昨 <span style='color:blue; font-weight:bold'>成交量</span>："
        f"{today_str} / {yest_str}"
        f"（<span style='color:blue; font-weight:bold'>達成:</span> {rate_str}, 富邦api）"
    )

def get_price_change_and_kbar(c1: float, c2: float, o: float) -> str:
    """
    判斷現價 vs 昨收、今開，回傳字串 "(漲跌 / K棒色)"。
    同時附加昨收 -> 現價 的漲跌百分比（黑色、非粗體），若無法計算則不顯示百分比。
    四捨五入使用 Decimal ROUND_HALF_UP 到小數後兩位。
    """
    pct_html = ""
    pct_color = "black"  # 預設顏色
    
    try:
        if (c2 is not None) and (c1 is not None) and float(c2) != 0:
            # 使用 Decimal 以確保穩定的四捨五入（half-up）
            d_c1 = Decimal(str(c1))
            d_c2 = Decimal(str(c2))
            pct = (d_c1 - d_c2) / d_c2 * Decimal("100")
            pct_display = pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            # 根據漲跌決定顏色
            if d_c1 > d_c2:
                pct_color = "#ef4444"  # 紅色
            elif d_c1 < d_c2:
                pct_color = "#16a34a"  # 綠色
            else:
                pct_color = "black"    # 黑色
            
            pct_html = f" <span style='color:{pct_color}; font-weight:normal'>{pct_display:+.2f}%</span>"
    except Exception:
        pct_html = ""

    # 漲跌（漲紅跌綠平黑）
    try:
        if c1 > c2:
            change_str = "<span style='color:#ef4444; font-weight:bold'>價漲</span>"
        elif c1 < c2:
            change_str = "<span style='color:#16a34a; font-weight:bold'>價跌</span>"
        else:
            change_str = "<span style='color:black; font-weight:bold'>價平</span>"
    except Exception:
        change_str = "<span style='color:black; font-weight:bold'>價平</span>"

    # K棒色
    try:
        if c1 > o:
            kbar_str = "📕K"
        elif c1 < o:
            kbar_str = "📗K"
        else:
            kbar_str = "平K"
    except Exception:
        kbar_str = "平K"

    return f" ({change_str}{pct_html} / {kbar_str})"


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
        baseline5, deduction5, ded1_5, ded2_5, ded3_5, prev_baseline5 = get_baseline_and_deduction(stock_id, today_date)
        
        # 取得週K棒和月K棒的基準價、扣抵值、前基準
        w_baseline, w_deduction, w_prev_baseline = get_week_month_baseline_and_deduction(stock_id, today_date, period='W', n=5)
        m_baseline, m_deduction, m_prev_baseline = get_week_month_baseline_and_deduction(stock_id, today_date, period='M', n=5)
        
        # 後面 col_mid / col_right 都可用
        ma5  = compute_ma_with_today(stock_id, today_date, c1, 5)
        ma10 = compute_ma_with_today(stock_id, today_date, c1, 10)
        ma24 = compute_ma_with_today(stock_id, today_date, c1, 24)

        col_left, col_mid, col_right = st.columns([3, 2, 2])

        with col_left:
            extra_info = get_price_change_and_kbar(c1, c2, o)
            st.markdown(
                f"- **今日(<span style='color:red'>{today_date[5:]}</span>)收盤價**"
                f"<span style='color:blue; font-weight:bold'>(現價)：{c1}</span>{extra_info}",
                unsafe_allow_html=True,
            )


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
                
                # 顯示「未來N天的壓力(...)升/降 ...%」詞條（用 5 日基準與四個扣抵計算）
                def _fmt(v):
                    try:
                        return float(v)
                    except Exception:
                        return None

                ded_vals_raw = [deduction5, ded1_5, ded2_5, ded3_5]
                ded_vals = [float(x) for x in ded_vals_raw if x is not None]

                if ded_vals and (baseline5 is not None) and float(baseline5) != 0:
                    
                    # 使用 Decimal 做精確四捨五入 (ROUND_HALF_UP) 到小數第2位
                    avg_dec = sum(Decimal(str(x)) for x in ded_vals) / Decimal(len(ded_vals))
                    avg_rounded = avg_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                    base_dec = Decimal(str(baseline5))
                    pct_dec = (avg_dec - base_dec) / base_dec * Decimal("100")
                    pct_rounded = pct_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                    if pct_dec > 0:
                        arrow = "<b>上升</b> 📈"
                    elif pct_dec < 0:
                        arrow = "<b>下降</b> 📉"
                    else:
                        arrow = "持平"

                    # 若四個扣都存在則顯示「未來4天」，否則顯示實際可用天數
                    days_label = 4 if len(ded_vals) == 4 else len(ded_vals)

                    # ===== 新增：比較 昨基(prev_baseline5) 與 基(baseline5)，產生前綴詞（並顯示乖離率） =====
                    prefix = ""
                    try:
                        if (prev_baseline5 is not None) and (baseline5 is not None):
                            # 使用 Decimal 做精確計算與四捨五入
                            pb_dec = Decimal(str(prev_baseline5))
                            b_dec = Decimal(str(baseline5))
                            if pb_dec == 0:
                                # 無法計算乖離率
                                pct_suffix = ""
                            else:
                                prev_pct_dec = (b_dec - pb_dec) / pb_dec * Decimal("100")
                                prev_pct_rounded = prev_pct_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                                pct_suffix = f" ({float(prev_pct_rounded):+.2f}%)"

                            if pb_dec < b_dec:
                                prefix = f"<b style='color:blue'>今壓上升</b>📈<span style='color:blue'>{pct_suffix}</span> "
                            elif pb_dec > b_dec:
                                prefix = f"<b style='color:blue'>今壓下降</b>📉<span style='color:blue'>{pct_suffix}</span> "
                            else:
                                prefix = f"<b style='color:blue'>今壓持平</b>➖<span style='color:blue'>{pct_suffix}</span> "
                    except Exception:
                        prefix = ""

                    st.markdown(
                        f"- {prefix} ⚡ 未來{days_label}天的<b>壓力</b>({float(avg_rounded):.2f}) {arrow} <b>{float(pct_rounded):+.2f}%</b>",
                        unsafe_allow_html=True,
                    )
                else:
                    # 資料不足時回退顯示原本扣位，方便除錯
                    def _fmt_str(v):
                        try:
                            return f"{float(v):.2f}"
                        except Exception:
                            return "—"
                    st.markdown(
                        f"- 扣1：<b>{_fmt_str(ded1_5)}</b>　扣2：<b>{_fmt_str(ded2_5)}</b>　扣3：<b>{_fmt_str(ded3_5)}</b>",
                        unsafe_allow_html=True,
                    )
                
                # === 顯示週K和月K的基準價、扣抵值、前基準與壓力變化 ===
                
                # 週K資訊
                if w_baseline is not None:
                    w_baseline_str = f"{w_baseline:.2f}"
                    w_deduction_str = f"{w_deduction:.2f}" if w_deduction is not None else "—"
                    w_prev_baseline_str = f"{w_prev_baseline:.2f}" if w_prev_baseline is not None else "—"
                    
                    # 計算本週壓力變化 (基準 vs 前基準)
                    week_current_pressure = ""
                    if w_prev_baseline is not None and w_prev_baseline != 0:
                        week_pct = (w_baseline - w_prev_baseline) / w_prev_baseline * 100
                        if week_pct > 0:
                            week_current_pressure = f"本週壓力上升📈(<span style='color:red'>+{week_pct:.2f}%</span>)⚡"
                        elif week_pct < 0:
                            week_current_pressure = f"本週壓力下降📉(<span style='color:green'>{week_pct:.2f}%</span>)⚡"
                        else:
                            week_current_pressure = "本週壓力持平⚡"
                    
                    # 計算下週壓力變化 (扣抵 vs 基準)
                    week_next_pressure = ""
                    if w_deduction is not None and w_baseline != 0:
                        week_next_pct = (w_deduction - w_baseline) / w_baseline * 100
                        if week_next_pct > 0:
                            week_next_pressure = f" 下週壓力上升📈(<span style='color:red'>+{week_next_pct:.2f}%</span>)"
                        elif week_next_pct < 0:
                            week_next_pressure = f" 下週壓力下降📉(<span style='color:green'>{week_next_pct:.2f}%</span>)"
                        else:
                            week_next_pressure = " 下週壓力持平"
                    
                    st.markdown(
                        f"""
                        - {week_current_pressure}{week_next_pressure}
                          <details style='margin-left: 20px;'>
                            <summary style='cursor: pointer; font-size:12px; color:#999; list-style: none;'>📊 詳細數據</summary>
                            <div style='font-size:13px; color:#666; padding: 5px 0 0 20px;'>
                                前基準 {w_prev_baseline_str} → 基準 {w_baseline_str} → 扣抵 {w_deduction_str}
                            </div>
                          </details>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown("- 📊 <b>週K 5週均</b>: 資料不足", unsafe_allow_html=True)
                
                # 月K資訊
                if m_baseline is not None:
                    m_baseline_str = f"{m_baseline:.2f}"
                    m_deduction_str = f"{m_deduction:.2f}" if m_deduction is not None else "—"
                    m_prev_baseline_str = f"{m_prev_baseline:.2f}" if m_prev_baseline is not None else "—"
                    
                    # 計算本月壓力變化 (基準 vs 前基準)
                    month_current_pressure = ""
                    if m_prev_baseline is not None and m_prev_baseline != 0:
                        month_pct = (m_baseline - m_prev_baseline) / m_prev_baseline * 100
                        if month_pct > 0:
                            month_current_pressure = f"本月壓力上升📈(<span style='color:red'>+{month_pct:.2f}%</span>)⚡"
                        elif month_pct < 0:
                            month_current_pressure = f"本月壓力下降📉(<span style='color:green'>{month_pct:.2f}%</span>)⚡"
                        else:
                            month_current_pressure = "本月壓力持平⚡"
                    
                    # 計算下月壓力變化 (扣抵 vs 基準)
                    month_next_pressure = ""
                    if m_deduction is not None and m_baseline != 0:
                        month_next_pct = (m_deduction - m_baseline) / m_baseline * 100
                        if month_next_pct > 0:
                            month_next_pressure = f" 下月壓力上升📈(<span style='color:red'>+{month_next_pct:.2f}%</span>)"
                        elif month_next_pct < 0:
                            month_next_pressure = f" 下月壓力下降📉(<span style='color:green'>{month_next_pct:.2f}%</span>)"
                        else:
                            month_next_pressure = " 下月壓力持平"
                    
                    st.markdown(
                        f"""
                        - {month_current_pressure}{month_next_pressure}
                          <details style='margin-left: 20px;'>
                            <summary style='cursor: pointer; font-size:12px; color:#999; list-style: none;'>📊 詳細數據</summary>
                            <div style='font-size:13px; color:#666; padding: 5px 0 0 20px;'>
                                前基準 {m_prev_baseline_str} → 基準 {m_baseline_str} → 扣抵 {m_deduction_str}
                            </div>
                          </details>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown("- 📊 <b>月K 5月均</b>: 資料不足", unsafe_allow_html=True)


            else:
                st.markdown("- **基準價 / 扣抵值**：資料不足")


        with col_mid:
            st.markdown("**提示訊息：**")
            # ✅ 在這裡判斷，先把詞條加到 tips
            is_up   = is_uptrending_now(stock_id, today_date, c1, w1, m1, ma5, ma10, ma24, above_upward_wma5)
            is_down = is_downtrending_now(stock_id, today_date, c1, w2, m2, ma5, ma10, ma24)

            if is_up:
                tips.insert(0, "向上趨勢盤，帶量 破壓追價!")
            elif is_down:
                tips.insert(0, "向下趨勢盤，帶量 破撐離場!")
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

            # ⭐ 週/月達成率（含今日盤中）—— 計好等下接在詞條後面
            wm_rate = compute_week_month_volume_achievement(
                stock_id=stock_id,
                today_info=today,
                db_path="data/institution.db",
            )
            wk_rate = wm_rate.get("week", None)
            mo_rate = wm_rate.get("month", None)

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
                    wk_html = _stylize_week_month_tag(_inject_rate_after_volume(tags['week'], wk_rate))
                    mo_html = _stylize_week_month_tag(_inject_rate_after_volume(tags['month'], mo_rate))

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
            
            # 🔹 加入成交量預估
            from ui.volume_forecast import render_volume_forecast
            # 取得今日和昨日的成交量（張）
            today_vol = today.get('v', None)  # 富邦API回傳的是張
            yest_vol = v1 / 1000.0 if v1 is not None else None  # DB的是股，轉為張
            if today_vol is not None and yest_vol is not None:
                render_volume_forecast(float(today_vol), float(yest_vol))
            
            # 🔹 今/昨 成交量（移到預估量下方）
            st.markdown(f"- {format_daily_volume_line(today, v1)}", unsafe_allow_html=True)


        return today_date, c1, o, c2, h, l, w1, w2, m1, m2

    except Exception as e:
        st.warning(f"⚠️ 無法取得關鍵價位分析資料：{e}")
        return None
