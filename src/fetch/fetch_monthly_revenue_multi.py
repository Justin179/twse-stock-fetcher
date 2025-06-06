import sqlite3
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def fetch_monthly_revenue(stock_id):
    url = f"https://www.cmoney.tw/finance/{stock_id}/f00029"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    wait = WebDriverWait(driver, 10)
    table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.tb.tb2")))
    rows = table.find_elements(By.TAG_NAME, "tr")
    data = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) >= 4:
            year_month = cols[0].text.strip()
            monthly_revenue = cols[1].text.strip().replace(",", "")
            yoy_rate = cols[3].text.strip().replace("%", "")
            if year_month.isdigit() and len(year_month) == 6:
                data.append((stock_id, year_month, float(monthly_revenue), float(yoy_rate)))

    driver.quit()
    return data

def save_to_db(data, db_path="data/institution.db"):
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_revenue (
            stock_id TEXT,
            year_month TEXT,
            revenue REAL,
            yoy_rate REAL,
            PRIMARY KEY (stock_id, year_month)
        )
    """)
    for row in data:
        cursor.execute("""
            INSERT OR REPLACE INTO monthly_revenue
            (stock_id, year_month, revenue, yoy_rate)
            VALUES (?, ?, ?, ?)
        """, row)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    with open("my_stock_holdings.txt", "r", encoding="utf-8") as f:
        stock_list = [line.strip() for line in f if line.strip()]

    for stock_id in stock_list:
        print(f"📥 抓取 {stock_id} 月營收資料...")
        try:
            data = fetch_monthly_revenue(stock_id)
            print(f"✅ {stock_id} 共取得 {len(data)} 筆")
            save_to_db(data)
        except Exception as e:
            print(f"❌ {stock_id} 發生錯誤: {e}")

    print("💾 所有股票資料已處理完畢")
