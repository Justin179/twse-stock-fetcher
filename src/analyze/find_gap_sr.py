#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

python src/analyze/find_gap_sr.py --db data/institution.db --stock 2317

Find gap-based support/resistance from daily, weekly, monthly K bars stored in SQLite.

Definition of gap (ka: previous, kb: next):
- Up gap   : ka.high < kb.low  -> zone (ka.high, kb.low); **support edge = ka.high**
- Down gap : ka.low  > kb.high -> zone (kb.high, ka.low); **resistance edge = ka.low**
Touching (==) is NOT a gap.
"""
from __future__ import annotations

import argparse
import sqlite3
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


def _fmt_key_for_tf(val, timeframe: str) -> str:
    try:
        if timeframe == "D":
            # Expect ISO date string; keep only date part
            return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        pass
    s = str(val)
    return s[:10] if (timeframe == "D" and len(s) >= 10) else s


def _load_daily(conn: sqlite3.Connection, stock_id: str, limit_days: int) -> pd.DataFrame:
    sql = f"""
        SELECT stock_id, date as key, open, high, low, close, volume
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT {int(limit_days)}
    """
    df = pd.read_sql_query(sql, conn, params=[stock_id])
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)]
    return df.sort_values("key").reset_index(drop=True)


def _load_weekly(conn: sqlite3.Connection, stock_id: str, limit_weeks: int) -> pd.DataFrame:
    sql = f"""
        SELECT stock_id, year_week as key, open, high, low, close, volume
        FROM twse_prices_weekly
        WHERE stock_id = ?
        ORDER BY year_week DESC
        LIMIT {int(limit_weeks)}
    """
    df = pd.read_sql_query(sql, conn, params=[stock_id])
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)]
    return df.sort_values("key").reset_index(drop=True)


def _load_monthly(conn: sqlite3.Connection, stock_id: str, limit_months: int) -> pd.DataFrame:
    sql = f"""
        SELECT stock_id, year_month as key, open, high, low, close, volume
        FROM twse_prices_monthly
        WHERE stock_id = ?
        ORDER BY year_month DESC
        LIMIT {int(limit_months)}
    """
    df = pd.read_sql_query(sql, conn, params=[stock_id])
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)]
    return df.sort_values("key").reset_index(drop=True)


def _get_c1(conn: sqlite3.Connection, stock_id: str, c1_override: Optional[float]) -> float:
    if c1_override is not None:
        return float(c1_override)
    row = pd.read_sql_query(
        "SELECT close FROM twse_prices WHERE stock_id = ? ORDER BY date DESC LIMIT 1",
        conn, params=[stock_id]
    )
    if row.empty or pd.isna(row.iloc[0]["close"]):
        raise RuntimeError(f"找不到 {stock_id} 的最新收盤價（twse_prices）。")
    return float(row.iloc[0]["close"])


def _scan_gaps(df: pd.DataFrame, timeframe: str, c1: float) -> List[Dict]:
    out: List[Dict] = []
    n = len(df)
    if n < 2:
        return out

    for i in range(1, n):
        ka = df.iloc[i-1]
        kb = df.iloc[i]

        ka_low, ka_high = float(ka["low"]), float(ka["high"])
        kb_low, kb_high = float(kb["low"]), float(kb["high"])

        # Up gap -> edge at ka.high (support)
        if ka_high < kb_low:
            gap_low = ka_high
            gap_high = kb_low
            edge_price = ka_high
            gap_type = "up"
        # Down gap -> edge at ka.low (resistance)
        elif ka_low > kb_high:
            gap_low = kb_high
            gap_high = ka_low
            edge_price = ka_low
            gap_type = "down"
        else:
            continue  # overlap/touch -> not a gap

        role = "support" if c1 > edge_price else "resistance" if c1 < edge_price else "at_edge"

        out.append({
            "timeframe": timeframe,
            "gap_type": gap_type,
            "edge_price": round(edge_price, 3),
            "role": role,
            "ka_key": _fmt_key_for_tf(ka["key"], timeframe),
            "kb_key": _fmt_key_for_tf(kb["key"], timeframe),
            "gap_low": round(gap_low, 3),
            "gap_high": round(gap_high, 3),
            "gap_width": round(gap_high - gap_low, 3),
            "c1": c1,
        })
    return out


def find_gap_support_resistance(
    conn: sqlite3.Connection,
    stock_id: str,
    c1_override: Optional[float] = None,
    days: int = 270,
    weeks: int = 52,
    months: int = 12,
) -> pd.DataFrame:
    c1 = _get_c1(conn, stock_id, c1_override)
    daily = _load_daily(conn, stock_id, days)
    weekly = _load_weekly(conn, stock_id, weeks)
    monthly = _load_monthly(conn, stock_id, months)

    rows: List[Dict] = []
    rows += _scan_gaps(daily, "D", c1)
    rows += _scan_gaps(weekly, "W", c1)
    rows += _scan_gaps(monthly, "M", c1)

    df = pd.DataFrame(rows, columns=[
        "timeframe", "gap_type", "edge_price", "role",
        "ka_key", "kb_key", "gap_low", "gap_high", "gap_width", "c1"
    ])
    role_rank = {"resistance": 0, "support": 1, "at_edge": 2}
    tf_rank = {"M": 0, "W": 1, "D": 2}
    if not df.empty:
        df["role_rank"] = df["role"].map(role_rank)
        df["tf_rank"] = df["timeframe"].map(tf_rank)
        # 排序：角色 → edge_price(大到小) → 時間框架(M,W,D)
        df = df.sort_values(["role_rank", "edge_price", "tf_rank"], ascending=[True, False, True]) \
               .drop(columns=["role_rank", "tf_rank"])
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description="Find gap-based support/resistance from daily/weekly/monthly K bars.")
    ap.add_argument("--db", default="data/institution.db", help="SQLite DB path")
    ap.add_argument("--stock", required=True, help="Stock ID, e.g., 2317")
    ap.add_argument("--c1", type=float, default=None, help="Override current price (optional)")
    ap.add_argument("--days", type=int, default=270)
    ap.add_argument("--weeks", type=int, default=52)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--save_csv", default=None)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        df = find_gap_support_resistance(conn, args.stock, args.c1, args.days, args.weeks, args.months)
        if df.empty:
            print("查無缺口資料。")
            return
        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            print(df.to_string(index=False))
        if args.save_csv:
            df.to_csv(args.save_csv, index=False, encoding="utf-8-sig")
            print(f"\nCSV 已輸出：{args.save_csv}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
