
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

DB_PATH = "data/institution.db"
TABLE_NAME = "twse_prices"

def init_db():
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
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

def convert_roc_to_ad(roc_date_str):
    try:
        roc_year, month, day = map(int, roc_date_str.split("/"))
        ad_year = roc_year + 1911
        return f"{ad_year}-{month:02d}-{day:02d}"
    except:
        return None

def parse_number(text):
    return float(
        text.replace(",", "")
            .replace("\xa0", "")
            .replace("&nbsp;", "")
            .strip()
    )

def fetch_price_with_selenium(stock_id, year, month):
    url = f"https://stock.wearn.com/cdata.asp?Year={year}&month={month:02d}&kind={stock_id}"
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(2)

    data = []
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "table.mobile_img tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 6:
                try:
                    date_text = cols[0].text.strip()
                    date = convert_roc_to_ad(date_text)
                    open_price = parse_number(cols[1].text)
                    high = parse_number(cols[2].text)
                    low = parse_number(cols[3].text)
                    close = parse_number(cols[4].text)
                    volume = int(parse_number(cols[5].text))
                    data.append((stock_id, date, open_price, high, low, close, volume))
                except Exception as e:
                    print(f"⚠️ 資料解析錯誤: {e}")
    finally:
        driver.quit()
    return data

def save_to_db(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0
    for row in data:
        cursor.execute(f"""
            INSERT OR IGNORE INTO {TABLE_NAME}
            (stock_id, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, row)
        if cursor.rowcount > 0:
            inserted += 1
    conn.commit()
    conn.close()
    return inserted

def main():
    stock_id = "3066"
    init_db()
    total = 0
    for year, month in [(114, 5), (114, 6)]:
        print(f"🔁 抓取 {stock_id} - {year}/{month:02d}...")
        records = fetch_price_with_selenium(stock_id, year, month)
        print(f"📊 共抓到 {len(records)} 筆")
        inserted = save_to_db(records)
        print(f"✅ 寫入 {inserted} 筆")
        total += inserted
    print(f"🎉 共新增 {total} 筆")

if __name__ == "__main__":
    main()
