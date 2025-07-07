import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = "data/institution.db"

def get_stock_high_low(stock_id="2330"):
    today = datetime.today()
    current_year, current_week, _ = today.isocalendar()

    Path("data").mkdir(exist_ok=True)

    # ✅ 改為讀取 high / low 欄位
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, stock_id, high, low FROM twse_prices WHERE stock_id = ?",
        conn, params=(stock_id,)
    )
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.isocalendar().year
    df["week"] = df["date"].dt.isocalendar().week
    df["month"] = df["date"].dt.month

    # 🔍 尋找最近有資料的上一週
    prev_week = current_week - 1
    year = current_year
    for _ in range(10):  # 最多往前推 10 週
        week_df = df[(df["year"] == year) & (df["week"] == prev_week)]
        if not week_df.empty:
            week_high = week_df["high"].max()
            week_low = week_df["low"].min()
            break
        prev_week -= 1
        if prev_week <= 0:
            year -= 1
            prev_week = 52
    else:
        week_high = week_low = None

    # 🔍 上個月
    prev_month = today.month - 1 or 12
    prev_month_year = today.year - 1 if today.month == 1 else today.year
    month_df = df[(df["date"].dt.year == prev_month_year) & (df["date"].dt.month == prev_month)]

    if not month_df.empty:
        month_high = month_df["high"].max()
        month_low = month_df["low"].min()
    else:
        month_high = month_low = None

    print(f"\n📈 {stock_id} 最近一週（週 {prev_week}）股價：")
    print(f"   高點：{week_high}，低點：{week_low}")
    print(f"📆 {stock_id} 上個月（{prev_month_year} 年 {prev_month} 月）股價：")
    if month_high is not None:
        print(f"   高點：{month_high}，低點：{month_low}")
    else:
        print("   ❌ 查無資料")

if __name__ == "__main__":
    get_stock_high_low("2330")
