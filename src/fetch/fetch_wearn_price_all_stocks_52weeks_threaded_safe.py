import requests
import sqlite3
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tqdm import tqdm
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import argparse

DB_PATH = "data/institution.db"
TABLE = "twse_prices"
PROGRESS_LOG = "wearn_completed.log"
MAX_RETRIES = 3
THREADS = 6
'''
➤ 預設（抓當月）
python fetch_wearn_price_all_stocks_52weeks_threaded_safe.py
➤ 自訂（抓過去 13 個月）
python fetch_wearn_price_all_stocks_52weeks_threaded_safe.py --months 13

'''
lock = threading.Lock()

def init_db():
    Path("data").mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
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

def get_all_stock_ids():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_id FROM stock_meta WHERE market IN ('市', '櫃') ORDER BY stock_id ASC")
        rows = cursor.fetchall()
    return [row[0] for row in rows]

def load_progress():
    if Path(PROGRESS_LOG).exists():
        with open(PROGRESS_LOG, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def mark_complete(stock_id):
    with lock:
        with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
            f.write(str(stock_id) + "\n")

def fetch_monthly_data(stock_id: str, roc_year: int, month: int):
    url = f"https://stock.wearn.com/cdata.asp?Year={roc_year}&month={month:02d}&kind={stock_id}"
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=10)
            resp.encoding = "big5"
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", {"class": "mobile_img"})
            if not table:
                return []
            rows = table.find_all("tr", class_=["stockalllistbg1", "stockalllistbg2"])
            data_list = []
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 6:
                    continue
                try:
                    roc_date = cols[0].text.strip()
                    ad_date = convert_roc_to_ad(roc_date)
                    open_price = parse_number(cols[1].text)
                    high_price = parse_number(cols[2].text)
                    low_price = parse_number(cols[3].text)
                    close_price = parse_number(cols[4].text)
                    volume = parse_number(cols[5].text, integer=True)
                    data_list.append((stock_id, ad_date, open_price, high_price, low_price, close_price, volume))
                except:
                    continue
            return data_list
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f"❌ {stock_id} {roc_year}/{month:02d} 失敗: {e}")
            time.sleep(1)
    return []

def convert_roc_to_ad(roc_date_str):
    try:
        roc_year, month, day = map(int, roc_date_str.split("/"))
        ad_year = roc_year + 1911
        return f"{ad_year}-{month:02d}-{day:02d}"
    except:
        return None

def parse_number(text, integer=False):
    text = text.replace(",", "").replace("\xa0", "").strip()
    return int(text) if integer else float(text)

def save_to_db(records):
    inserted = 0
    with lock: # ✅ 避免 DB lock
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            for record in records:
                cursor.execute(f"""
                    INSERT OR IGNORE INTO {TABLE} (stock_id, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, record)
                if cursor.rowcount > 0:
                    inserted += 1
            conn.commit()
    return inserted

def process_stock(stock_id, months):
    total_inserted = 0
    for y, m in months:
        data = fetch_monthly_data(stock_id, y, m)
        total_inserted += save_to_db(data)
    mark_complete(stock_id)
    return stock_id, total_inserted

def get_target_months(months_back: int = 1):
    today = datetime.today()
    months = [(today - relativedelta(months=i)).replace(day=1) for i in range(months_back)]
    return [(d.year - 1911, d.month) for d in months]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=1, help="要抓取幾個月的資料（預設=1，即當月）")
    args = parser.parse_args()

    init_db()
    all_stocks = get_all_stock_ids()

    completed = load_progress()
    stock_list = [s for s in all_stocks if s not in completed]

    month_params = get_target_months(args.months)

    print(f"🧪 本次待處理股票數：{len(stock_list)}，已完成數：{len(completed)}，月份數：{len(month_params)}")

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(process_stock, sid, month_params): sid for sid in stock_list}
        for f in tqdm(as_completed(futures), total=len(futures), desc="處理中", ncols=80):
            stock_id, inserted = f.result()
            tqdm.write(f"📌 {stock_id} 新增 {inserted} 筆")

if __name__ == "__main__":
    main()
