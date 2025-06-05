import os
import sqlite3
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

def fetch_holder_concentration(stock_id):
    url = f"https://norway.twsthr.info/StockHolders.aspx?stock={stock_id}"

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "Details"))
        )
        time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        table = soup.find("table", id="Details")
        rows = table.find_all("tr")

        data = []
        for i, row in enumerate(rows):
            cols = row.find_all("td")
            if len(cols) >= 14:
                date = cols[2].text.strip().replace("/", "")
                avg_shares = cols[5].text.strip().replace(",", "")
                ratio_1000 = cols[13].text.strip()

                if date.isdigit() and len(date) == 8:
                    data.append((stock_id, date, avg_shares, ratio_1000))

        driver.quit()
        return data

    except Exception as e:
        driver.quit()
        print(f"❌ {stock_id} 發生錯誤：", e)
        return []

if __name__ == "__main__":
    with open("my_stock_holdings.txt", "r", encoding="utf-8") as f:
        stock_list = [line.strip() for line in f if line.strip()]

    db_path = os.path.join("data", "institution.db")
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 建表（如不存在）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS holder_concentration (
            stock_id TEXT,
            date TEXT,
            avg_shares REAL,
            ratio_1000 REAL,
            PRIMARY KEY (stock_id, date)
        )
    """)

    for stock_id in stock_list:
        print(f"🔍 處理 {stock_id} ...")
        records = fetch_holder_concentration(stock_id)
        success = 0
        for row in records:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO holder_concentration (stock_id, date, avg_shares, ratio_1000)
                    VALUES (?, ?, ?, ?)
                """, row)
                success += 1
            except Exception as e:
                print(f"⚠️ INSERT 發生錯誤: {e}")
        conn.commit()
        print(f"✅ {stock_id} 成功寫入 {success} 筆")

    conn.close()
    print("🎉 所有資料處理完成")