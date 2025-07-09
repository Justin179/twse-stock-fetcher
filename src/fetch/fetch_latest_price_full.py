# fetch_latest_price_full.py

import requests
import os
import sqlite3
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv("FINMIND_TOKEN")
DB_PATH = "data/institution.db"

def fetch_and_store_price(stock_id="2330"):
    if not TOKEN:
        print("❌ 請在 .env 檔案中設定 FINMIND_TOKEN")
        return

    url = "https://api.finmindtrade.com/api/v4/data"
    headers = {"Authorization": f"Bearer {TOKEN}"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS twse_prices (
            stock_id TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (stock_id, date)
        )
    """)
    count_inserted = 0
    for i in range(63):
        date_str = (datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d")
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": date_str,
            "end_date": date_str,
        }

        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        rows = data.get("data", [])
        # print([row["date"] for row in rows])  # 只印出日期
        
        for row in rows:
            cursor.execute("""
                INSERT OR IGNORE INTO twse_prices (stock_id, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                stock_id,
                row["date"],
                row["open"],
                row["max"],
                row["min"],
                row["close"],
                row["Trading_Volume"]
            ))
            if cursor.rowcount > 0:
                print(f"✅ 補上 {stock_id} - {row['date']}")
                count_inserted += 1

    conn.commit()
    conn.close()
    if count_inserted == 0:
        print(f"ℹ️ {stock_id} 沒有需要補的資料（過去15天內皆已存在）")

if __name__ == "__main__":
    fetch_and_store_price("2330")
