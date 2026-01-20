from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import pandas as pd
import sqlite3


DEFAULT_DB_PATH = "data/institution.db"


@dataclass(frozen=True)
class TrendResult:
    token: str  # one of: ✅ ✔️ ➖ ❌ 💀
    label: str  # human label, e.g. "強多頭"


def _is_iso_year_week(year_week: str) -> bool:
    # Expected: YYYY-WW (zero padded)
    if not isinstance(year_week, str) or len(year_week) != 7:
        return False
    if year_week[4] != "-":
        return False
    y, w = year_week.split("-", 1)
    return y.isdigit() and w.isdigit()


def _current_year_week(today_date: str) -> str:
    today = pd.to_datetime(today_date)
    year, week, _ = today.isocalendar()
    return f"{int(year)}-{int(week):02d}"


def _current_year_month(today_date: str) -> str:
    today = pd.to_datetime(today_date)
    return f"{today.year}-{today.month:02d}"


def _load_close_series(
    conn: sqlite3.Connection,
    table: str,
    stock_id: str,
    key_col: str,
    close_col: str = "close",
    limit: int = 80,
) -> pd.DataFrame:
    # Order by key desc then reverse; key is YYYY-MM or YYYY-WW or YYYY-MM-DD.
    df = pd.read_sql_query(
        f"""
        SELECT {key_col} AS k, {close_col} AS close
        FROM {table}
        WHERE stock_id = ?
        ORDER BY {key_col} DESC
        LIMIT ?
        """,
        conn,
        params=(stock_id, int(limit)),
    )
    if df.empty:
        return df

    df = df.dropna(subset=["k", "close"]).copy()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    # reverse to ascending time
    return df.iloc[::-1].reset_index(drop=True)


def _classify_ma_trend(close: Sequence[float], windows: Tuple[int, int, int] = (5, 10, 24)) -> TrendResult:
    w_fast, w_mid, w_slow = windows
    s = pd.Series(list(close), dtype="float64")

    # Need at least (slow + 1) to check slope of MA(slow)
    if len(s) < w_slow + 1:
        return TrendResult(token="➖", label="盤整")

    ma_fast = s.rolling(w_fast).mean()
    ma_mid = s.rolling(w_mid).mean()
    ma_slow = s.rolling(w_slow).mean()

    # Last and previous values must exist
    last = len(s) - 1
    prev = len(s) - 2
    for ma in (ma_fast, ma_mid, ma_slow):
        if pd.isna(ma.iloc[last]) or pd.isna(ma.iloc[prev]):
            return TrendResult(token="➖", label="盤整")

    f0, m0, s0 = float(ma_fast.iloc[last]), float(ma_mid.iloc[last]), float(ma_slow.iloc[last])
    f1, m1, s1 = float(ma_fast.iloc[prev]), float(ma_mid.iloc[prev]), float(ma_slow.iloc[prev])

    bull_order = (f0 > m0) and (m0 > s0)
    bear_order = (f0 < m0) and (m0 < s0)

    up = (f0 > f1) and (m0 > m1) and (s0 > s1)
    down = (f0 < f1) and (m0 < m1) and (s0 < s1)

    if bull_order and up:
        return TrendResult(token="✅", label="強多頭")
    if bull_order:
        return TrendResult(token="✔️", label="弱多頭")
    if bear_order and down:
        return TrendResult(token="💀", label="強空頭")
    if bear_order:
        return TrendResult(token="❌", label="弱空頭")
    return TrendResult(token="➖", label="盤整")


def compute_trend_tokens(
    stock_id: str,
    today_date: str,
    today_close: Optional[float] = None,
    db_path: str = DEFAULT_DB_PATH,
    daily_windows: Tuple[int, int, int] = (5, 10, 24),
    weekly_windows: Tuple[int, int, int] = (5, 10, 24),
    monthly_windows: Tuple[int, int, int] = (5, 10, 24),
) -> Tuple[TrendResult, TrendResult, TrendResult]:
    """Return (daily, weekly, monthly) trend results.

    - Daily uses twse_prices (optionally patches/append today's close for real-time).
    - Weekly uses twse_prices_weekly (includes current in-progress week; optionally patches close).
    - Monthly uses twse_prices_monthly (includes current in-progress month; optionally patches close).

    Any failure returns ➖ for that timeframe.
    """

    try:
        conn = sqlite3.connect(db_path)
    except Exception:
        r = TrendResult(token="➖", label="盤整")
        return r, r, r

    try:
        # Daily
        df_d = _load_close_series(conn, "twse_prices", stock_id, key_col="date", limit=180)
        if today_close is not None and not df_d.empty:
            # Patch or append today's close (DB may not have today's row during market hours)
            last_key = str(df_d["k"].iloc[-1])
            if last_key == str(today_date):
                df_d.loc[df_d.index[-1], "close"] = float(today_close)
            else:
                df_d = pd.concat(
                    [df_d, pd.DataFrame([{ "k": str(today_date), "close": float(today_close)}])],
                    ignore_index=True,
                )
        daily = _classify_ma_trend(df_d["close"].tolist(), windows=daily_windows) if not df_d.empty else TrendResult("➖", "盤整")

        # Weekly (include current week; patch close for real-time if provided)
        df_w = _load_close_series(conn, "twse_prices_weekly", stock_id, key_col="year_week", limit=180)
        if today_close is not None and not df_w.empty:
            cur_yw = _current_year_week(today_date)
            if isinstance(df_w["k"].iloc[-1], str) and _is_iso_year_week(df_w["k"].iloc[-1]) and df_w["k"].iloc[-1] == cur_yw:
                df_w.loc[df_w.index[-1], "close"] = float(today_close)
        weekly = _classify_ma_trend(df_w["close"].tolist(), windows=weekly_windows) if not df_w.empty else TrendResult("➖", "盤整")

        # Monthly (include current month; patch close for real-time if provided)
        df_m = _load_close_series(conn, "twse_prices_monthly", stock_id, key_col="year_month", limit=180)
        if today_close is not None and not df_m.empty:
            cur_ym = _current_year_month(today_date)
            if isinstance(df_m["k"].iloc[-1], str) and df_m["k"].iloc[-1] == cur_ym:
                df_m.loc[df_m.index[-1], "close"] = float(today_close)
        monthly = _classify_ma_trend(df_m["close"].tolist(), windows=monthly_windows) if not df_m.empty else TrendResult("➖", "盤整")

        return daily, weekly, monthly
    except Exception:
        r = TrendResult(token="➖", label="盤整")
        return r, r, r
    finally:
        try:
            conn.close()
        except Exception:
            pass


def format_trend_phrase(daily: TrendResult, weekly: TrendResult, monthly: TrendResult) -> str:
    return f"短{daily.token} 中{weekly.token} 長{monthly.token}"


def get_trend_phrase(
    stock_id: str,
    today_date: str,
    today_close: Optional[float] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> str:
    d, w, m = compute_trend_tokens(stock_id=stock_id, today_date=today_date, today_close=today_close, db_path=db_path)
    return format_trend_phrase(d, w, m)
