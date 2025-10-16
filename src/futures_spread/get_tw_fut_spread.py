# -*- coding: utf-8 -*-
# get_tw_fut_spread.py — 台股「台指期近月 vs 加權指數」期現價差（單檔 CLI）
# python .\src\futures_spread\get_tw_fut_spread.py 直接拿「最新可得值」
# python .\src\futures_spread\get_tw_fut_spread.py --date 2025-10-01

from __future__ import annotations

import os, io, re, argparse
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Tuple

import requests
import pandas as pd
import yfinance as yf

# ---------- 時區 ----------
try:
    from zoneinfo import ZoneInfo
    TPE = ZoneInfo("Asia/Taipei")
except Exception:
    TPE = timezone(timedelta(hours=8))

def today_tpe() -> date:
    return datetime.now(TPE).date()

# ---------- 現貨 (^TWII) ----------
def get_twii_close_for_date(the_date: date, lookback_days: int = 30) -> Tuple[date, float]:
    """回傳 (實際交易日, 收盤價)；若 the_date 無資料則向前回溯到最近交易日"""
    t = yf.Ticker("^TWII")
    start = (the_date - timedelta(days=lookback_days + 10)).strftime("%Y-%m-%d")
    end   = (the_date + timedelta(days=2)).strftime("%Y-%m-%d")
    hist = t.history(start=start, end=end, interval="1d", actions=False, auto_adjust=False)
    if hist.empty:
        raise RuntimeError("^TWII 歷史資料為空")

    idx = pd.to_datetime(hist.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(TPE)
    hist = hist.copy()
    hist["trade_date"] = idx.date

    sub = hist[hist["trade_date"] <= the_date]
    if sub.empty:
        raise RuntimeError(f"^TWII 在 {the_date}（含）以前查無收盤資料")

    row = sub.iloc[-1]
    return row["trade_date"], float(row["Close"])

# ---------- 期貨 (FinMind TaiwanFuturesDaily, TX 近月) ----------
FINMIND_API = "https://api.finmindtrade.com/api/v4/data"

def _parse_contract_date(x) -> Optional[date]:
    if pd.isna(x): return None
    s = str(x).strip()
    if re.fullmatch(r"\d{6}", s):      # e.g. 202510
        return datetime.strptime(s, "%Y%m").date().replace(day=1)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return datetime.strptime(s, "%Y-%m-%d").date()
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None

def get_tx_near_month_price_on(the_date: date,
                               token: Optional[str] = None) -> Tuple[str, float]:
    """回傳 (近月YYYYMM, 當日價格)。若該天沒有，外層會回溯。"""
    ds = the_date.strftime("%Y-%m-%d")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"dataset": "TaiwanFuturesDaily", "data_id": "TX",
              "start_date": ds, "end_date": ds}
    r = requests.get(FINMIND_API, headers=headers, params=params, timeout=20)
    j = r.json()
    if not j.get("data"):
        raise RuntimeError(j.get("msg") or "FinMind 無資料")

    df = pd.DataFrame(j["data"])
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[df["date"] == the_date]
    if "trading_session" in df.columns:
        df = df[df["trading_session"].isin(["regular", "position", "day"])]
    if df.empty:
        raise RuntimeError("指定日期沒有台指期日盤資料")

    if "contract_date" not in df.columns:
        raise RuntimeError("缺少 contract_date 欄位")
    df["contract_date_parsed"] = df["contract_date"].map(_parse_contract_date)
    df = df.dropna(subset=["contract_date_parsed"])
    if df.empty:
        raise RuntimeError("contract_date 格式無法解析")

    row = df.loc[df["contract_date_parsed"].idxmin()]  # 近月
    price = None
    # 🔧 修改：優先取 close，因為 FinMind 的 position 時段 settlement_price 可能是 0
    for col in ("close", "close_price", "settlement_price", "end_price"):
        if col in df.columns and pd.notna(row.get(col)):
            val = float(row[col])
            if val > 0:  # 確保價格有效（> 0）
                price = val
                break
    if price is None:
        raise RuntimeError("找不到價格欄位（settlement/close）")

    ym = row["contract_date_parsed"].strftime("%Y%m")
    return ym, price

def get_tx_near_month_with_lookback(base_day: date,
                                    token: Optional[str],
                                    lookback_days: int = 30) -> Tuple[date, str, float]:
    """向前回溯直到找到 TX 近月價；回傳 (實際交易日, 近月YYYYMM, 價格)"""
    cur = base_day
    for _ in range(lookback_days + 1):
        try:
            ym, px = get_tx_near_month_price_on(cur, token=token)
            return cur, ym, px
        except Exception:
            cur -= timedelta(days=1)
    raise RuntimeError(f"台指期近月價回溯 {lookback_days} 天仍無資料")

# ---------- 整體：期現價差 ----------
def compute_tw_fut_spread(on_day: Optional[date] = None,
                          token: Optional[str] = None) -> dict:
    base = on_day or today_tpe()
    fut_day, ym, fut_px = get_tx_near_month_with_lookback(base, token)
    spot_day, spot_px   = get_twii_close_for_date(fut_day)  # 對齊到期貨那天
    spread_pts = fut_px - spot_px
    return {
        "trade_date": fut_day.strftime("%Y-%m-%d"),
        "spot_close": spot_px,
        "future_near_month": ym,
        "future_price": fut_px,
        "spread_pts": spread_pts,
    }

# ---------- CLI ----------
def fmt_num(x: float) -> str:
    return f"{x:,.2f}"

def main():
    ap = argparse.ArgumentParser(description="台股 期現價差（TX 近月 vs ^TWII 收盤）")
    ap.add_argument("--date", help="指定日期 YYYY-MM-DD（預設=台北時間今天；會自動回溯到最近有期貨資料的一天）")
    ap.add_argument("--token", help="FinMind token；也可用環境變數 FINMIND_TOKEN")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    args = ap.parse_args()

    qd = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    token = args.token or os.environ.get("FINMIND_TOKEN")

    res = compute_tw_fut_spread(qd, token)

    if args.json:
        import json
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    # 輸出格式參考你的圖
    print(f"{res['trade_date']}")
    print(f"● 加權股價指數(L): {fmt_num(res['spot_close'])}")
    print(f"● 台指期(L)      : {fmt_num(res['future_price'])}  （近月 {res['future_near_month']}）")
    print(f"● 台指期減加權股價指數(R): {fmt_num(res['spread_pts'])}")

if __name__ == "__main__":
    main()
