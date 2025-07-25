import sqlite3
import pandas as pd
from pathlib import Path
from gen_filtered_report_db import fetch_stock_history_from_db

def get_weekly_last_close_prices(df: pd.DataFrame, num_weeks: int = 6):
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    df["year_week"] = df.index.to_series().apply(lambda d: f"{d.isocalendar().year}-{d.isocalendar().week:02d}")
    last_per_week = df.groupby("year_week").tail(1).copy()

    last_closes = last_per_week["Close"].tail(num_weeks)
    return last_closes

if __name__ == "__main__":
    stock_code = "2891"
    db_path = Path(__file__).resolve().parents[2] / "data" / "institution.db"

    with sqlite3.connect(db_path) as conn:
        df = fetch_stock_history_from_db(conn, stock_code)

        if df.empty:
            print(f"❌ 無資料: {stock_code}")
        else:
            
            closes = get_weekly_last_close_prices(df, num_weeks=6)
            print("📘 最近 6 週每週最後一日收盤價（最舊 → 最新）:")
            print(closes)

            if len(closes) >= 6:
                current = closes.iloc[-1]
                five_weeks_ago = closes.iloc[-6]
                is_upward = current > five_weeks_ago
                print(f"\n🔍 本週收盤: {current} vs 前5週: {five_weeks_ago}")
                print("📈 5週均線上彎？", "✅ 是" if is_upward else "❌ 否")
            else:
                print("⚠️ 週資料不足 6 週，無法比較")
