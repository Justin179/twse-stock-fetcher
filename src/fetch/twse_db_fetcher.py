
import sqlite3
import pandas as pd
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from dateutil.relativedelta import relativedelta
from tqdm import tqdm

DB_PATH = "data/institution.db"

def get_twse_month_data(stock_code: str, date: datetime) -> list:
    date_str = date.strftime("%Y%m01")
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={stock_code}"
    try:
        response = httpx.get(url, timeout=10.0, verify=False)
        data = response.json()
        return data.get("data", [])
    except:
        return []

def convert_to_df(data_rows: list) -> pd.DataFrame:
    records = []
    for row in data_rows:
        try:
            roc_date = row[0].replace("/", "-")
            y, m, d = map(int, roc_date.split("-"))
            date = datetime(y + 1911, m, d).strftime("%Y-%m-%d")
            open_ = float(row[3].replace(",", ""))
            high = float(row[4].replace(",", ""))
            low = float(row[5].replace(",", ""))
            close = float(row[6].replace(",", ""))
            volume = int(row[1].replace(",", ""))
            records.append([date, open_, high, low, close, volume])
        except:
            continue
    return pd.DataFrame(records, columns=["Date", "Open", "High", "Low", "Close", "Volume"])

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

def save_to_db(stock_id: str, df: pd.DataFrame):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR IGNORE INTO twse_prices (stock_id, date, open, high, low, close, volume)
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

def fetch_twse_history_to_db(stock_code: str):
    today = datetime.today()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM twse_prices WHERE stock_id = ? ORDER BY date DESC LIMIT 1", (stock_code,))
    row = cursor.fetchone()
    last_date = datetime.strptime(row[0], "%Y-%m-%d") if row else today - relativedelta(months=12)
    conn.close()

    all_data = []

    for i in range(12):
        date = today - relativedelta(months=i)
        if date < last_date.replace(day=1):
            continue
        rows = get_twse_month_data(stock_code, date)
        df_month = convert_to_df(rows)
        if df_month.empty:
            return (stock_code, [date.strftime('%Y-%m')])
        else:
            save_to_db(stock_code, df_month)

    return None

def read_stock_list(file_path="stock_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

if __name__ == "__main__":
    init_db()
    stock_list = read_stock_list("stock_list.txt")
    skip_count = 0
    success_count = 0
    failed_summary = []

    print(f"📦 開始抓取 TWSE 歷史資料（共 {len(stock_list)} 檔）...")

    for stock_code in tqdm(stock_list, desc="處理中", ncols=80):
        result = fetch_twse_history_to_db(stock_code)
        if result is None:
            success_count += 1
        else:
            skip_count += 1
            code, months = result
            failed_summary.append(f"{code}")

    print("\n📊 抓取完畢")
    print(f"✅ 成功寫入 DB：{success_count} 檔")
    print(f"⚠️ 資料不足未寫入：{skip_count} 檔")

    if failed_summary:
        print("\n🚫 缺少資料的股票代號：")
        print(" ".join(failed_summary))
