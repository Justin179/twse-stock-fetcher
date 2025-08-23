# analyze/moving_average_monthly.py
# -*- coding: utf-8 -*-
"""
上彎 5 個月均線（MMA5）判斷工具

規則說明：
  以 today_date 為月份定錨：
    a = 本月月收盤（以現價 today_close 視為本月月收盤）
    b = 上月月收盤
    c = 上上月月收盤
    d = 上上上月月收盤
    e = 上上上上月月收盤
    f = 上上上上上月月收盤
  mma5 = (a+b+c+d+e) / 5
  條件1：a(=today_close) > mma5           → 站上 5 個月均線
  條件2：a(=today_close) > f              → 5 個月均線上彎
  兩條件同時為 True → 現價站上「上彎」的 5 個月均線
"""

from typing import Tuple, Optional
import pandas as pd
from common.db_helpers import fetch_close_history_from_db


def _prepare_monthly_last_closes(stock_id: str) -> pd.DataFrame:
    """
    從 DB 取得每日收盤，轉為每月最後一個交易日的收盤價序列。
    回傳欄位至少包含：['date', 'close', 'ym']，按日期排序。
    """
    df = fetch_close_history_from_db(stock_id)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df["ym"] = df["date"].dt.strftime("%Y-%m")
    last_trading_per_month = df.groupby("ym").tail(1).copy()
    last_trading_per_month = last_trading_per_month.sort_values("date").reset_index(drop=True)
    return last_trading_per_month


def compute_mma5_with_today(
    stock_id: str,
    today_date: str,
    today_close: float,
) -> Optional[Tuple[float, float, float, float, float, float, float]]:
    """
    計算 mma5 與 a~f：
      回傳 (mma5, a, b, c, d, e, f)；資料不足則回傳 None
    - 若本月(以 today_date 為定錨)尚未入庫，會人工補上一筆「本月月收盤 = today_close」
    """
    last_trading_per_month = _prepare_monthly_last_closes(stock_id)
    if last_trading_per_month.empty:
        return None

    target_date = pd.to_datetime(today_date)
    this_month_key = target_date.strftime("%Y-%m")

    # 若本月不存在 → 人工補入一筆，close 用 today_close
    if this_month_key not in last_trading_per_month["ym"].values:
        fake_row = {
            "date": pd.to_datetime(today_date),
            "close": float(today_close),
            "ym": this_month_key,
        }
        last_trading_per_month = pd.concat(
            [last_trading_per_month, pd.DataFrame([fake_row])],
            ignore_index=True,
        ).sort_values("date").reset_index(drop=True)

    # 找到本月位置
    pos = last_trading_per_month.index[
        last_trading_per_month["ym"] == this_month_key
    ][0]

    # 需要 a~f（本月+往前5月）共 6 個月
    if pos < 5:
        # 月資料不足
        return None

    # a = 本月，用 today_close 覆蓋；b~f 取序列
    a = float(today_close)
    b = float(last_trading_per_month.iloc[pos - 1]["close"])
    c = float(last_trading_per_month.iloc[pos - 2]["close"])
    d = float(last_trading_per_month.iloc[pos - 3]["close"])
    e = float(last_trading_per_month.iloc[pos - 4]["close"])
    f = float(last_trading_per_month.iloc[pos - 5]["close"])

    mma5 = round((a + b + c + d + e) / 5.0, 2)   # 🔹 四捨五入到小數點後兩位
    return mma5, a, b, c, d, e, f


def is_price_above_upward_mma5(
    stock_id: str,
    today_date: str,
    today_close: float,
    *,
    debug_print: bool = True,
) -> bool:
    """
    判斷是否「現價站上 上彎的 5 個月均線」：
      cond1: a(=today_close) > mma5
      cond2: a(=today_close) > f
    兩者皆 True → 回傳 True
    會依需求印出 today_date, c1, mma5, a, b, c, d, e, f（確認後可關閉 debug_print）。
    """
    result = compute_mma5_with_today(stock_id, today_date, today_close)
    if result is None:
        if debug_print:
            print(f"[MMA5 DEBUG] stock={stock_id} today_date={today_date} 資料不足（月資料需至少 6 個月含本月）")
        return False

    mma5, a, b, c, d, e, f = result

    if debug_print:
        # 依你的要求輸出所有關鍵數值（確認無誤後可移除或設 debug_print=False）
        print(
            f"[MMA5 DEBUG] stock={stock_id} today_date={today_date} "
            f"c1(a)={a} mma5={mma5} a={a} b={b} c={c} d={d} e={e} f={f}"
        )

    cond1 = a > mma5
    cond2 = a > f
    return cond1 and cond2
