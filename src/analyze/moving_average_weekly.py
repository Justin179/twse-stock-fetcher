# analyze/moving_average_weekly.py
# -*- coding: utf-8 -*-
"""
上彎 5 週均線（WMA5）判斷工具

規則：
  以 today_date 為週定錨：
    a = 本週週收盤（用 today_close 視為本週週收盤）
    b,c,d,e = 前 1~4 週的週收盤
    f = 前 5 週的週收盤
  wma5 = (a+b+c+d+e) / 5
  cond1: a(=today_close) > wma5         → 站上 5 週均
  cond2: a(=today_close) > f            → 5 週均線上彎
  cond1 & cond2 → True
"""

from typing import Optional, Tuple
import pandas as pd
from common.db_helpers import fetch_close_history_from_db


def _prepare_weekly_last_closes(stock_id: str) -> pd.DataFrame:
    """把日K轉成「每週最後一個交易日收盤」序列（含 year_week），依日期排序。"""
    df = fetch_close_history_from_db(stock_id)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["year_week"] = df["date"].apply(
        lambda d: f"{d.isocalendar().year}-{d.isocalendar().week:02d}"
    )
    w = df.groupby("year_week").tail(1).copy()
    w = w.sort_values("date").reset_index(drop=True)
    return w


def compute_wma5_with_today(
    stock_id: str,
    today_date: str,
    today_close: float,
) -> Optional[Tuple[float, float, float, float, float, float, float]]:
    """
    回傳 (wma5, a, b, c, d, e, f)，資料不足回傳 None。
    本週若尚未入庫，會人工補上一筆（close=today_close）。
    """
    w = _prepare_weekly_last_closes(stock_id)
    if w.empty:
        return None

    target = pd.to_datetime(today_date)
    this_week_key = f"{target.isocalendar().year}-{target.isocalendar().week:02d}"

    # 本週不存在 → 人工補入
    if this_week_key not in w["year_week"].values:
        fake = {"date": target, "close": float(today_close), "year_week": this_week_key}
        w = pd.concat([w, pd.DataFrame([fake])], ignore_index=True)
        w = w.sort_values("date").reset_index(drop=True)

    pos = w.index[w["year_week"] == this_week_key][0]

    # 需要 a~f（本週 + 往前 5 週）共 6 週
    if pos < 5:
        return None

    a = float(today_close)                       # 本週（用 today_close 覆蓋）
    b = float(w.iloc[pos - 1]["close"])
    c = float(w.iloc[pos - 2]["close"])
    d = float(w.iloc[pos - 3]["close"])
    e = float(w.iloc[pos - 4]["close"])
    f = float(w.iloc[pos - 5]["close"])

    wma5 = (a + b + c + d + e) / 5.0
    return wma5, a, b, c, d, e, f


def get_wma5_position_flags_with_today(
    stock_id: str,
    today_date: str,
    today_close: float,
    *,
    debug_print: bool = False,
) -> Optional[Tuple[float, bool, bool]]:
    """回傳 (wma5, above_wma5, upward_wma5)，資料不足回傳 None。

    - above_wma5: a(=today_close) > wma5
    - upward_wma5: a(=today_close) > f (前 5 週週收盤)
    """
    res = compute_wma5_with_today(stock_id, today_date, today_close)
    if res is None:
        if debug_print:
            print(
                f"[WMA5 DEBUG] stock={stock_id} today_date={today_date} 資料不足（至少需 6 週含本週）"
            )
        return None

    wma5, a, b, c, d, e, f = res
    above_wma5 = a > wma5
    upward_wma5 = a > f

    if debug_print:
        wma5_2dp = round(wma5, 2)
        print(
            f"[WMA5 DEBUG] stock={stock_id} today_date={today_date} "
            f"above_wma5={above_wma5} upward_wma5={upward_wma5} wma5={wma5_2dp} "
            f"a={a} b={b} c={c} d={d} e={e} f={f}"
        )

    return wma5, above_wma5, upward_wma5


def is_price_above_upward_wma5(
    stock_id: str,
    today_date: str,
    today_close: float,
    *,
    debug_print: bool = False,
) -> bool:
    """
    判斷是否「現價站上上彎 5 週均線」；
    debug_print=True 時會印出 wma5 與 a~f 供查核。
    """
    flags = get_wma5_position_flags_with_today(
        stock_id,
        today_date,
        today_close,
        debug_print=debug_print,
    )
    if flags is None:
        return False
    _wma5, above_wma5, upward_wma5 = flags
    return above_wma5 and upward_wma5
