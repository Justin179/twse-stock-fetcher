import sqlite3
import pandas as pd
from datetime import datetime

"""
補上 monthly_revenue 資料庫中缺少的 monthly_avg_close 和 monthly_last_close 欄位
這些欄位是從 twse_prices 資料庫中計算得來的。
finmind_db_fetcher.py 可以補上 twse_prices 資料庫的資料。
"""

DB_PATH = "data/institution.db"

def get_missing_rows():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT stock_id, year_month
        FROM monthly_revenue
        WHERE monthly_avg_close IS NULL OR monthly_last_close IS NULL
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def compute_monthly_prices_from_db(stock_id: str, year_month: str):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"""
        SELECT date, close FROM twse_prices
        WHERE stock_id = '{stock_id}'
    """, conn)

    conn.close()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["ym"] = df["date"].dt.strftime("%Y%m")

    df_month = df[df["ym"] == year_month]

    if df_month.empty:
        return None, None

    avg = round(df_month["close"].mean(), 2)
    last = round(df_month["close"].iloc[-1], 2)
    return avg, last

def update_price_to_db(stock_id: str, year_month: str, avg: float, last: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE monthly_revenue
        SET monthly_avg_close = ?, monthly_last_close = ?
        WHERE stock_id = ? AND year_month = ?
    """, (avg, last, stock_id, year_month))

    if cursor.rowcount > 0:
        print(f"[OK] 補上 {stock_id} {year_month} → avg: {avg}, last: {last}")
    else:
        print(f"[SKIP] 找不到 row 可更新：{stock_id} {year_month}")

    conn.commit()
    conn.close()

def main():
    missing_list = get_missing_rows()
    print(f"🔍 共需補上 {len(missing_list)} 筆資料")

    for stock_id, year_month in missing_list:
        avg, last = compute_monthly_prices_from_db(stock_id, year_month)
        if avg is not None and last is not None:
            update_price_to_db(stock_id, year_month, avg, last)
        else:
            print(f"[FAIL] {stock_id} {year_month} 無法從 twse_prices 計算資料")

if __name__ == "__main__":
    main()
