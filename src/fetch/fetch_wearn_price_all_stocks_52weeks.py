
import requests
import sqlite3
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tqdm import tqdm

DB_PATH = "data/institution.db"
TABLE = "twse_prices"

def init_db():
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

def get_all_stock_ids():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT stock_id FROM stock_meta WHERE market IN ('市', '櫃') ORDER BY stock_id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def fetch_monthly_data(stock_id: str, roc_year: int, month: int):
    url = f"https://stock.wearn.com/cdata.asp?Year={roc_year}&month={month:02d}&kind={stock_id}"
    resp = requests.get(url)
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
            data_list.append((
                stock_id, ad_date, open_price, high_price, low_price, close_price, volume
            ))
        except:
            continue
    return data_list

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0
    for record in records:
        cursor.execute(f"""
            INSERT OR IGNORE INTO {TABLE} (stock_id, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, record)
        if cursor.rowcount > 0:
            inserted += 1
    conn.commit()
    conn.close()
    return inserted

def main():
    init_db()
    stock_list = get_all_stock_ids()[:5] # 只處理前 5 支股票以測試
    print(f"🧪 測試抓取股票：{stock_list}")

    today = datetime.today()
    months = []
    for i in range(13):  # 抓近 13 個月（約 52 週）
        target = today - relativedelta(months=i)
        roc_year = target.year - 1911
        months.append((roc_year, target.month))

    for stock_id in tqdm(stock_list, desc="所有股票處理中", ncols=80):
        total_inserted = 0
        for y, m in months:
            data = fetch_monthly_data(stock_id, y, m)
            count = save_to_db(data)
            total_inserted += count
        print(f"📌 {stock_id} 共新增 {total_inserted} 筆")

if __name__ == "__main__":
    main()
