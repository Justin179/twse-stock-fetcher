# src/fetch/fetch_index_yahoo_to_db_v2.py

import os
import sqlite3
import pandas as pd
import yfinance as yf
from dateutil.relativedelta import relativedelta
from datetime import datetime


def fetch_twii_sample():
    today = datetime.today()
    start_date = (today - relativedelta(months=69)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')

    df = yf.download("^TWII", start=start_date, end=end_date, progress=False)
    if df.empty:
        print("❌ 沒有抓到 TWS (^TWII) 的資料")
        return pd.DataFrame()

    df = df.reset_index()
    print(f"✅ A")
    print(df.head())

    # 清理欄位名稱 & 加上 stock_id
    df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    print(f"✅ A1")
    print(df)
    df = df[['date', 'close', 'high', 'low', 'open', 'volume']].copy()
    print(f"✅ A2")
    print(df)
    df['stock_id'] = '^TWII'

    # 只保留最後 5 筆
    df = df.tail(5).copy()
    print(f"✅ A3")
    print(df)

    return df[['stock_id', 'date', 'open', 'high', 'low', 'close', 'volume']]


def save_to_db(df, db_path="data/institution.db"):
    abs_path = os.path.abspath(db_path)
    print(f"📁 DB 實際寫入路徑：{abs_path}")

    conn = sqlite3.connect(abs_path)
    cursor = conn.cursor()
    success_count = 0

    for count, (_, row) in enumerate(df.iterrows(), 1):
        try:
            stock_id = str(row["stock_id"])
            date_obj = row["date"]

            if pd.isna(date_obj):
                raise ValueError("❌ 日期是 NaT")

            date = pd.to_datetime(date_obj).strftime('%Y-%m-%d')  # 轉為文字格式
            open_ = round(float(row["open"]), 2)
            high = round(float(row["high"]), 2)
            low = round(float(row["low"]), 2)
            close = round(float(row["close"]), 2)
            volume = int(row["volume"])

            cursor.execute(
                """
                INSERT OR IGNORE INTO twse_prices (stock_id, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (stock_id, date, open_, high, low, close, volume)
            )

            if cursor.rowcount > 0:
                success_count += 1
        except Exception as e:
            print(f"⚠️ 第 {count} 筆寫入失敗: {e}")

    conn.commit()
    print(f"✅ conn.total_changes = {conn.total_changes}")
    print(f"✅ 成功寫入 {success_count} 筆")
    conn.close()


if __name__ == "__main__":
    df_test = fetch_twii_sample()
    save_to_db(df_test)
