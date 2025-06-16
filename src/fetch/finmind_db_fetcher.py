import sqlite3
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from tqdm import tqdm
import sys
from FinMind.data import DataLoader

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

def get_existing_dates(stock_id: str) -> set:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM twse_prices WHERE stock_id = ?", (stock_id,))
    rows = cursor.fetchall()
    conn.close()
    return set(row[0] for row in rows)

def save_to_db(stock_id: str, df: pd.DataFrame):
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

def fetch_with_finmind(stock_id: str):
    today = datetime.today()
    start_date = (today - relativedelta(months=38)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')

    dl = DataLoader()
    df = dl.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=start_date,
        end_date=end_date,
    )

    if df.empty:
        return (stock_id, "No data")

    existing_dates = get_existing_dates(stock_id)
    df = df[~df["date"].isin(existing_dates)]

    if df.empty:
        return (stock_id, "Already up-to-date")

    save_to_db(stock_id, df)
    return None

def read_stock_list(file_path="stock_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "stock_list.txt"
    init_db()
    stock_list = read_stock_list(input_file)

    skip, done, msg = 0, 0, []

    print(f"📦 使用 FinMind 抓取近 38 個月歷史資料（共 {len(stock_list)} 檔）...")

    for stock_id in tqdm(stock_list, desc="處理中", ncols=80):
        result = fetch_with_finmind(stock_id)
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
