#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggregate daily OHLCV (twse_prices) into weekly & monthly K-bars and store them
into two new SQLite tables:
  - twse_prices_weekly (PRIMARY KEY: stock_id, year_week  e.g., "2025-34")
  - twse_prices_monthly (PRIMARY KEY: stock_id, year_month e.g., "2025-08")

設計重點
- 週/月邊界：與你現有程式一致
    * 週：使用 ISO 週 (isocalendar year-week)，格式 "YYYY-WW"
    * 月：使用 "YYYY-MM"
- 聚合規則（每檔、每期）
    open  = 該期第一個交易日的開盤價
    high  = 該期所有交易日 high 的最大值
    low   = 該期所有交易日 low 的最小值
    close = 該期最後一個交易日的收盤價
    volume= 該期所有交易日 volume 的加總
- today_date（選擇性）：若提供，僅聚合 <= today_date 的日K資料作為定錨。
  （若 today_date 當天未入庫，則本週/本月以資料庫中最新日期為準；
   之後可再擴充「注入今日盤中數據」的版本。）

使用方式
    python aggregate_ohlcv_weekly_monthly.py \
        --db data/institution.db \
        --today 2025-08-22 \
        --stock 2330 2317

    # 僅指定 DB，匯總所有股票至今天（以 DB 內最大日期作為定錨）
    python aggregate_ohlcv_weekly_monthly.py --db data/institution.db --today 2025-08-22

"""

from __future__ import annotations

import argparse
import sqlite3
from typing import Iterable, List, Optional, Tuple

import pandas as pd


def ensure_tables(conn: sqlite3.Connection) -> None:
    """Create weekly/monthly tables if not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS twse_prices_weekly (
            stock_id   TEXT NOT NULL,
            year_week  TEXT NOT NULL,     -- e.g., '2025-34' (ISO year-week)
            open       REAL,
            high       REAL,
            low        REAL,
            close      REAL,
            volume     INTEGER,
            PRIMARY KEY (stock_id, year_week)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS twse_prices_monthly (
            stock_id   TEXT NOT NULL,
            year_month TEXT NOT NULL,     -- e.g., '2025-08'
            open       REAL,
            high       REAL,
            low        REAL,
            close      REAL,
            volume     INTEGER,
            PRIMARY KEY (stock_id, year_month)
        )
        """
    )
    # 便利索引（查詢單一股或掃描全部時更快；非必要，可保留）
    conn.execute("CREATE INDEX IF NOT EXISTS idx_twse_prices_weekly_sid ON twse_prices_weekly(stock_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_twse_prices_monthly_sid ON twse_prices_monthly(stock_id)")


def load_daily(
    conn: sqlite3.Connection,
    stock_ids: Optional[Iterable[str]] = None,
    today_date: Optional[str] = None,
) -> pd.DataFrame:
    """Load daily K from twse_prices with optional stock filter and anchor date."""
    base_sql = """
        SELECT stock_id, date, open, high, low, close, volume
        FROM twse_prices
    """
    conds: List[str] = []
    params: List[object] = []

    if stock_ids:
        placeholders = ",".join(["?"] * len(list(stock_ids)))
        conds.append(f"stock_id IN ({placeholders})")
        params.extend(list(stock_ids))

    if today_date:
        conds.append("date <= ?")
        params.append(today_date)

    if conds:
        base_sql += " WHERE " + " AND ".join(conds)

    base_sql += " ORDER BY stock_id, date"

    df = pd.read_sql_query(base_sql, conn, params=params, parse_dates=["date"])

    # ---- 缺值與「零價」處理：確保只用有效日K ----
    # 任一 OHLC 為 NaN 或 0 的日K，視為「無效交易日」→ 排除。
    before_len = len(df)
    mask_valid = (
        df["open"].notna() & df["high"].notna() & df["low"].notna() & df["close"].notna() &
        (df["open"] != 0) & (df["high"] != 0) & (df["low"] != 0) & (df["close"] != 0)
    )
    invalid = df[~mask_valid]
    if not invalid.empty:
        sample = invalid.head(5)[["stock_id", "date", "open", "high", "low", "close"]]
        print(f"ℹ️ 已排除 {len(invalid)} 筆 OHLC=0/NaN 的日K（樣本）：\n{sample}")
    df = df[mask_valid].copy()

    # ---- 缺值處理：確保匯總後一定有完整 OHLC ----
    # 若日K有缺值（停牌等），直接略過該日，以避免週/月 open/close 產生 NaN
    before = len(df)
    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
    after = len(df)
    if before != after:
        # 僅作運行訊息，不影響功能
        print(f"ℹ️ 已忽略 {before - after} 筆 OHLC 缺值的日K（以確保週/月 K 完整）。")
    # 量若缺值，視為 0（不影響高低價統計）
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0)

    return df


def aggregate_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to weekly bars using ISO year-week boundaries."""
    if df.empty:
        return pd.DataFrame(columns=["stock_id", "year_week", "open", "high", "low", "close", "volume"])

    # Sort so groupby('first'/'last') aligns with chronological order
    df_sorted = df.sort_values(["stock_id", "date"]).copy()

    iso = df_sorted["date"].dt.isocalendar()
    df_sorted["year_week"] = iso.year.astype(str) + "-" + iso.week.map(lambda x: f"{int(x):02d}")

    wk = (
        df_sorted
        .groupby(["stock_id", "year_week"], as_index=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
    )

    # volume 轉為 int，避免 NaN（當日資料若有缺失，預設視為 0）
    wk["volume"] = wk["volume"].fillna(0).astype("int64")
    return wk


def aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to monthly bars using YYYY-MM boundaries."""
    if df.empty:
        return pd.DataFrame(columns=["stock_id", "year_month", "open", "high", "low", "close", "volume"])

    df_sorted = df.sort_values(["stock_id", "date"]).copy()
    df_sorted["year_month"] = df_sorted["date"].dt.strftime("%Y-%m")

    mk = (
        df_sorted
        .groupby(["stock_id", "year_month"], as_index=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
    )
    mk["volume"] = mk["volume"].fillna(0).astype("int64")
    return mk


def upsert_weekly(conn: sqlite3.Connection, wk: pd.DataFrame) -> int:
    """UPSERT weekly rows with ON CONFLICT ... DO UPDATE (就地更新，不先刪再插)。"""
    if wk.empty:
        return 0
    rows: List[Tuple] = list(
        wk[["stock_id", "year_week", "open", "high", "low", "close", "volume"]]
        .itertuples(index=False, name=None)
    )
    conn.executemany(
        """
        INSERT INTO twse_prices_weekly
            (stock_id, year_week, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stock_id, year_week) DO UPDATE SET
            open   = excluded.open,
            high   = excluded.high,
            low    = excluded.low,
            close  = excluded.close,
            volume = excluded.volume
        """,
        rows,
    )
    return len(rows)


def upsert_monthly(conn: sqlite3.Connection, mk: pd.DataFrame) -> int:
    """UPSERT monthly rows with ON CONFLICT ... DO UPDATE (就地更新，不先刪再插)。"""
    if mk.empty:
        return 0
    rows: List[Tuple] = list(
        mk[["stock_id", "year_month", "open", "high", "low", "close", "volume"]]
        .itertuples(index=False, name=None)
    )
    conn.executemany(
        """
        INSERT INTO twse_prices_monthly
            (stock_id, year_month, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stock_id, year_month) DO UPDATE SET
            open   = excluded.open,
            high   = excluded.high,
            low    = excluded.low,
            close  = excluded.close,
            volume = excluded.volume
        """,
        rows,
    )
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggregate daily OHLCV into weekly/monthly K-bars in SQLite.")
    ap.add_argument("--db", default="data/institution.db", help="SQLite DB path (default: data/institution.db)")
    ap.add_argument("--today", dest="today_date", default=None, help="Anchor date YYYY-MM-DD (optional)")
    ap.add_argument("--stock", nargs="*", default=None, help="One or more stock IDs to aggregate (default: all)")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        ensure_tables(conn)

        df_daily = load_daily(conn, stock_ids=args.stock, today_date=args.today_date)
        if df_daily.empty:
            print("❗ twse_prices 無符合條件的資料，未進行聚合。")
            return

        wk = aggregate_weekly(df_daily)
        mk = aggregate_monthly(df_daily)

        n_w = upsert_weekly(conn, wk)
        n_m = upsert_monthly(conn, mk)
        conn.commit()

        max_date = df_daily["date"].max().strftime("%Y-%m-%d")
        print(f"✅ 聚合完成（定錨到 {args.today_date or max_date}）。")
        print(f"   週K upsert: {n_w} 筆 → twse_prices_weekly")
        print(f"   月K upsert: {n_m} 筆 → twse_prices_monthly")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
