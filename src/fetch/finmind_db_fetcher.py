import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from tqdm import tqdm
from FinMind.data import DataLoader
import logging

DB_PATH = "data/institution.db"

# 初始化 log 系統
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_filename = log_dir / f"finmind_{datetime.today().strftime('%Y%m%d')}.txt"
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

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

def fetch_with_finmind(stock_id: str, request_count: int):
    today = datetime.today()
    start_date = (today - relativedelta(months=69)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')

    dl = DataLoader()
    df = dl.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=start_date,
        end_date=end_date,
    )

    # 記錄 request log
    logging.info(f"Request #{request_count}: {stock_id}")

    if df.empty:
        logging.warning(f"Request #{request_count}: {stock_id} - No data or API limit?")
        return (stock_id, "No data")

    existing_dates = get_existing_dates(stock_id)
    df = df[~df["date"].isin(existing_dates)]
    if df.empty:
        logging.info(f"Request #{request_count}: {stock_id} - Already up-to-date")
        return (stock_id, "Already up-to-date")

    save_to_db(stock_id, df)
    logging.info(f"Request #{request_count}: {stock_id} - Saved {len(df)} rows to DB")
    return None

def read_stock_list(file_path="shareholding_concentration_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "shareholding_concentration_list.txt"
    init_db()
    stock_list = read_stock_list(input_file)

    skip, done, msg, request_count = 0, 0, [], 0

    # ✅ 加入這段 log 分隔線
    logging.info("-" * 60)
    logging.info(f"🔄 新一輪執行開始（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    logging.info("-" * 60)

    print(f"📦 使用 FinMind 抓取近 69 個月歷史資料（共 {len(stock_list)} 檔）...")

    for stock_id in tqdm(stock_list, desc="處理中", ncols=80):
        request_count += 1
        result = fetch_with_finmind(stock_id, request_count)
        if result is None:
            done += 1
        else:
            skip += 1
            msg.append(f"{result[0]} ({result[1]})")

    print("\n📊 抓取完畢")
    print(f"✅ 成功寫入 DB：{done} 檔")
    print(f"⚠️ 跳過（無資料或已存在）：{skip} 檔")
    logging.info(f"總共 request 次數: {request_count}")
    logging.info(f"成功寫入: {done} 檔，跳過: {skip} 檔")

    if msg:
        print("\n🚫 跳過清單：")
        print(" / ".join(msg))
