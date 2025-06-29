
import requests
import sqlite3
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

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

def fetch_monthly_data(stock_id: str, roc_year: int, month: int):
    url = f"https://stock.wearn.com/cdata.asp?Year={roc_year}&month={month:02d}&kind={stock_id}"
    print(f"✅ 正在抓取 {roc_year}/{month:02d} 的資料，網址: {url}")
    resp = requests.get(url)
    resp.encoding = "big5"  # 網頁為繁中 big5 編碼
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", {"class": "mobile_img"})
    if not table:
        print(f"❌ 無法解析 {roc_year}/{month:02d} 的表格")
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
        except Exception as e:
            print(f"⚠️ 無法處理某列資料: {e}")
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
    stock_id = "3066"
    total_inserted = 0
    init_db()
    for y, m in [(114, 5), (114, 6)]:
        print(f"🔁 抓取 {y}/{m:02d} 資料...")
        data = fetch_monthly_data(stock_id, y, m)
        count = save_to_db(data)
        total_inserted += count
        print(f"✅ 成功寫入 {count} 筆")

    print(f"🎯 完成！總共新增 {total_inserted} 筆資料")

if __name__ == "__main__":
    main()
