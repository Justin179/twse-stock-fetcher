import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path
from dateutil.relativedelta import relativedelta
from tqdm import tqdm

DB_PATH = "data/institution.db"

def init_db():
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS yf_prices (
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

def save_to_db(stock_id: str, df: pd.DataFrame):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR IGNORE INTO yf_prices (stock_id, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            stock_id,
            row["Date"],
            row["Open"],
            row["High"],
            row["Low"],
            row["Close"],
            row["Volume"]
        ))
    conn.commit()
    conn.close()

def fetch_yf_history_to_db(stock_code: str):
    today = datetime.today()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM yf_prices WHERE stock_id = ? ORDER BY date DESC LIMIT 1", (stock_code,))
    row = cursor.fetchone()
    last_date = datetime.strptime(row[0], "%Y-%m-%d") if row else today - relativedelta(months=12)
    conn.close()

    start = last_date + relativedelta(days=1)
    end = today

    ticker = yf.Ticker(stock_code + ".TW")
    df = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    if df.empty:
        return (stock_code, [])
    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    df = df.rename(columns={
        "Open": "Open",
        "High": "High",
        "Low": "Low",
        "Close": "Close",
        "Volume": "Volume"
    })
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
    save_to_db(stock_code, df)
    return None

def read_stock_list(file_path="shareholding_concentration_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

if __name__ == "__main__":
    init_db()
    stock_list = read_stock_list("shareholding_concentration_list.txt")
    skip_count = 0
    success_count = 0
    failed_summary = []

    print(f"📦 開始抓取 YF 歷史資料（共 {len(stock_list)} 檔）...")

    for stock_code in tqdm(stock_list, desc="處理中", ncols=80):
        result = fetch_yf_history_to_db(stock_code)
        if result is None:
            success_count += 1
        else:
            skip_count += 1
            code, _ = result
            failed_summary.append(f"{code}")

    print("\n📊 抓取完畢")
    print(f"✅ 成功寫入 DB：{success_count} 檔")
    print(f"⚠️ 資料不足未寫入：{skip_count} 檔")

    if failed_summary:
        print("\n🚫 缺少資料的股票代號：")
        print(" ".join(failed_summary))