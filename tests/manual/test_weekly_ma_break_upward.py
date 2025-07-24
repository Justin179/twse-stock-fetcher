import sqlite3
import pandas as pd
from pathlib import Path
from gen_filtered_report_db import fetch_stock_history_from_db, calculate_weekly_ma

def check_break_upward_weekly_ma(df: pd.DataFrame) -> bool:
    try:
        df["WMA5"] = df.index.map(calculate_weekly_ma(df, weeks=5)["WMA5"])

        # 週均線上彎判斷：比較前5週與本週的最後收盤價
        df_temp = df.copy()
        df_temp.index = pd.to_datetime(df_temp.index)
        df_temp["year_week"] = df_temp.index.to_series().apply(lambda d: f"{d.isocalendar().year}-{d.isocalendar().week:02d}")
        last_per_week = df_temp.groupby("year_week").tail(1).copy()
        last_closes = last_per_week["Close"].tail(6)

        is_upward = False
        if len(last_closes) >= 6:
            current = last_closes.iloc[-1]
            print("📈 本週收盤:", current)
            five_weeks_ago = last_closes.iloc[-6]
            print("📈 前5週收盤:", five_weeks_ago)
            is_upward = current > five_weeks_ago

        result = is_upward
        return result

    except Exception as e:
        print("例外:", e)
        return False

if __name__ == "__main__":
    stock_code = "2317"
    db_path = Path(__file__).resolve().parents[2] / "data" / "institution.db"

    with sqlite3.connect(db_path) as conn:
        df = fetch_stock_history_from_db(conn, stock_code)

        if df.empty:
            print(f"❌ 無資料: {stock_code}")
        else:
            passed = check_break_upward_weekly_ma(df)
            print(f"\n📈 上彎5週均？ {'✅ 是' if passed else '❌ 否'}")
