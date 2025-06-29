
import sqlite3
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import pandas as pd
from tqdm import tqdm
from pathlib import Path

# 程式可以用，但刷免費 API 會有次數限制，需用付費的 FinMind Pro 這支程式才能用

DB_PATH = "data/institution.db"

def init_db():
    Path("data").mkdir(exist_ok=True)
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
    conn.commit()
    conn.close()

def get_all_stock_ids():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_id FROM stock_meta WHERE market IN ('市', '櫃')")
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

def get_existing_dates(stock_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM twse_prices WHERE stock_id = ?", (stock_id,))
    rows = cursor.fetchall()
    conn.close()
    return set(row[0] for row in rows)

def save_to_db(stock_id, df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
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
    conn.commit()
    conn.close()

def fetch_52week_data(stock_id):
    today = datetime.today()
    start_date = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')

    dl = DataLoader()
    df = dl.taiwan_stock_daily(stock_id=stock_id, start_date=start_date, end_date=end_date)
    if df.empty:
        return (stock_id, "No data")

    existing_dates = get_existing_dates(stock_id)
    df = df[~df["date"].isin(existing_dates)]
    if df.empty:
        return (stock_id, "Already up-to-date")

    save_to_db(stock_id, df)
    return None

def main():
    init_db()
    stock_list = get_all_stock_ids()
    print(f"📦 開始抓取所有上市與上櫃股票近 52 週歷史資料（共 {len(stock_list)} 檔）")

    skip, done, msg = 0, 0, []
    for stock_id in tqdm(stock_list, desc="處理中", ncols=80):
        result = fetch_52week_data(stock_id)
        if result is None:
            done += 1
        else:
            skip += 1
            msg.append(f"{result[0]} ({result[1]})")

    print("\n📊 抓取完畢")
    print(f"✅ 成功寫入 DB：{done} 檔")
    print(f"⚠️ 跳過（無資料或已存在）：{skip} 檔")
    if msg:
        print("\n🚫 跳過清單：")
        print(" / ".join(msg))

if __name__ == "__main__":
    main()
