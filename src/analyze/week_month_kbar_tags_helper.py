# src/common/week_month_kbar_tags_helper.py
# 純計算工具：回傳「上週 / 上月」兩條詞條字串，不依賴 Streamlit。
from __future__ import annotations
import sqlite3
from typing import Optional, Dict, Tuple
import pandas as pd

# ---------- 讀日K ----------
def _load_daily(db_path: str, stock_id: str, last_n: int = 270) -> pd.DataFrame:
    sql = f"""
        SELECT date, open, high, low, close, volume
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT {int(last_n)}
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(sql, conn, params=[stock_id], parse_dates=["date"])
    df = df.dropna(subset=["open","high","low","close"])
    df = df[(df["open"]>0) & (df["high"]>0) & (df["low"]>0) & (df["close"]>0)]
    return df.sort_values("date").reset_index(drop=True)

# ---------- 併入盤中（o/h/l/c1/v→今天列；v 以股計，若來源是「張」請乘 1000） ----------
def _attach_intraday(daily: pd.DataFrame, today: Optional[dict]) -> pd.DataFrame:
    if daily.empty or not today:
        return daily
    t_date_str = str(today.get("date") or "")
    if not t_date_str:
        return daily
    t_date = pd.to_datetime(t_date_str).normalize()

    def _f(k, default=None):
        try:
            v = today.get(k, None)
            return float(v) if v is not None else default
        except Exception:
            return default

    row_today = {
        "date": t_date,
        "open":  _f("o"),
        "high":  _f("h"),
        "low":   _f("l"),
        "close": _f("c1"),
        "volume": (_f("v", 0.0) or 0.0) * 1000.0,  # 張→股
    }
    df = daily.copy()
    mask = (df["date"].dt.normalize() == t_date)
    if mask.any():
        idx = df.index[mask][-1]
        for k, vv in row_today.items():
            df.at[idx, k] = vv
    else:
        df = pd.concat([df, pd.DataFrame([row_today])], ignore_index=True)
    return df.sort_values("date").reset_index(drop=True)

# ---------- 週/月聚合（與互動圖一致的做法） ----------
def _aggregate_weekly(daily_with_today: pd.DataFrame, last_n: int = 60) -> pd.DataFrame:
    if daily_with_today.empty:
        return pd.DataFrame(columns=["key","open","high","low","close","volume"])
    df = daily_with_today.copy()
    df["date"] = pd.to_datetime(df["date"])
    iso = df["date"].dt.isocalendar()
    df["year_week"] = iso.year.astype(str) + "-" + iso.week.map(lambda x: f"{int(x):02d}")
    out = (df.sort_values("date")
             .groupby("year_week", as_index=False)
             .agg(open=("open","first"), high=("high","max"),
                  low=("low","min"), close=("close","last"),
                  volume=("volume","sum"))
             .rename(columns={"year_week":"key"})
             .sort_values("key").reset_index(drop=True))
    return out.tail(int(last_n)).reset_index(drop=True)

def _aggregate_monthly(daily_with_today: pd.DataFrame, last_n: int = 36) -> pd.DataFrame:
    if daily_with_today.empty:
        return pd.DataFrame(columns=["key","open","high","low","close","volume"])
    df = daily_with_today.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    out = (df.sort_values("date")
             .groupby("year_month", as_index=False)
             .agg(open=("open","first"), high=("high","max"),
                  low=("low","min"), close=("close","last"),
                  volume=("volume","sum"))
             .rename(columns={"year_month":"key"})
             .sort_values("key").reset_index(drop=True))
    return out.tail(int(last_n)).reset_index(drop=True)

# ---------- 帶大量旗標（視窗=20；條件①：均量倍數且不量縮；條件②：相對前一根倍數） ----------
def _enrich_heavy_flags(df: pd.DataFrame,
                        ma_window: int = 20,
                        multiple_ma: float = 1.7,
                        multiple_prev: float = 1.5,
                        no_shrink_ratio: float = 0.8) -> pd.DataFrame:
    d = df.copy()
    d["v_maN"] = d["volume"].rolling(window=ma_window, min_periods=ma_window).mean()
    d["prev_volume"] = d["volume"].shift(1)
    cond_ma = (d["v_maN"].notna()) & (d["volume"] >= multiple_ma * d["v_maN"])
    cond_no_shrink = d["prev_volume"].notna() & (d["volume"] >= no_shrink_ratio * d["prev_volume"])
    d["is_heavy_ma"] = cond_ma & cond_no_shrink
    d["is_heavy_prev"] = d["prev_volume"].notna() & (d["volume"] >= multiple_prev * d["prev_volume"])
    d["is_heavy"] = d["is_heavy_ma"] | d["is_heavy_prev"]
    return d

# ---------- 分類 / 文案 ----------
def _classify_move(open_p: float, close_p: float, threshold_pct: float) -> Tuple[str, float]:
    if open_p is None or close_p is None or open_p <= 0:
        return ("持平", 0.0)
    pct = (close_p - open_p) / open_p * 100.0  # A→B（開→收）
    if abs(pct) < 1e-9: return ("持平", 0.0)
    if pct > 0:
        return ("大漲", pct) if pct > threshold_pct else ("漲", pct)
    else:
        return ("大跌", pct) if abs(pct) > threshold_pct else ("跌", pct)

def _has_long_upper_shadow(open_p: float, high_p: float, close_p: float) -> bool:
    upper = high_p - max(open_p, close_p)
    body  = abs(close_p - open_p)
    return (upper > 0) and (upper > body)

def _to_line(row: pd.Series, title: str, threshold_pct: float) -> str:
    o, h, c = float(row["open"]), float(row["high"]), float(row["close"])
    tag_move, pct = _classify_move(o, c, threshold_pct)
    tag_vol = "帶大量" if bool(row.get("is_heavy", False)) else "一般量"
    tag_wick = "，留長上影線" if _has_long_upper_shadow(o, h, c) else ""
    return f"{title} {tag_move}({pct:.2f}%) {tag_vol}{tag_wick}"

# ---------- 對外主函式 ----------
def get_week_month_tags(stock_id: str,
                        db_path: str = "data/institution.db",
                        today_info: Optional[dict] = None,
                        weekly_threshold_pct: float = 6.5,
                        monthly_threshold_pct: float = 15.0,
                        multiple_ma: float = 1.7,
                        multiple_prev: float = 1.5,
                        no_shrink_ratio: float = 0.8) -> Dict[str, str]:
    """
    回傳：
      {
        "week":  "上週 漲多(…%) 帶大量，留長上影線",
        "month": "上月 小跌(…%) 一般量"
      }
    """
    daily = _load_daily(db_path, stock_id, last_n=270)
    if daily.empty:
        return {"week":"上週 資料不足", "month":"上月 資料不足"}

    daily2 = _attach_intraday(daily, today_info or {})
    wk = _aggregate_weekly(daily2, last_n=60)
    mo = _aggregate_monthly(daily2, last_n=36)

    wk = _enrich_heavy_flags(wk, ma_window=20, multiple_ma=multiple_ma,
                             multiple_prev=multiple_prev, no_shrink_ratio=no_shrink_ratio)
    mo = _enrich_heavy_flags(mo, ma_window=20, multiple_ma=multiple_ma,
                             multiple_prev=multiple_prev, no_shrink_ratio=no_shrink_ratio)

    prev_w = wk.iloc[-2] if len(wk) >= 2 else None   # 倒數第二根＝上週
    prev_m = mo.iloc[-2] if len(mo) >= 2 else None   # 倒數第二根＝上月

    w_line = _to_line(prev_w, "上週", weekly_threshold_pct) if prev_w is not None else "上週 資料不足"
    m_line = _to_line(prev_m, "上月", monthly_threshold_pct) if prev_m is not None else "上月 資料不足"
    return {"week": w_line, "month": m_line}
