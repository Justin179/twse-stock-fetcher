# fetch_twii_close.py
import yfinance as yf
import pandas as pd
import argparse
from datetime import datetime, timedelta, date

def get_twii_close_for_date(the_date: date, lookback_days: int = 5) -> float:
    t = yf.Ticker("^TWII")
    start = (the_date - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end = (the_date + timedelta(days=1)).strftime("%Y-%m-%d")
    hist = t.history(start=start, end=end, interval="1d", actions=False, auto_adjust=False)

    if hist.empty:
        raise RuntimeError("^TWII 歷史資料為空")

    idx = pd.to_datetime(hist.index)
    hist = hist.copy()
    hist["trade_date"] = idx.date

    sub = hist[hist["trade_date"] <= the_date]
    if sub.empty:
        raise RuntimeError(f"^TWII 在 {the_date}（含）以前查無收盤資料")

    row = sub.iloc[-1]
    return float(row["Close"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抓取指定日期的加權股價指數收盤價 (^TWII)")
    parser.add_argument("--date", type=str, required=True, help="日期格式: YYYY-MM-DD")
    args = parser.parse_args()

    dt = datetime.strptime(args.date, "%Y-%m-%d").date()
    close = get_twii_close_for_date(dt)
    print(f"{dt} 加權股價指數收盤價: {close}")
