import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

"""
排程3: 更新 每個月的6號-14號，公司會公佈上個月的營收
INSERT OR IGNORE INTO monthly_revenue
"""
MAX_RETRIES = 3

def fetch_monthly_revenue(stock_id):
    url = f"https://www.cmoney.tw/finance/{stock_id}/f00029"

    for attempt in range(MAX_RETRIES):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

            if "查無資料" in driver.page_source or "無營收資料" in driver.page_source:
                print(f"⚠️  {stock_id} 無營收資料，直接跳過")
                driver.quit()
                return []

            wait = WebDriverWait(driver, 10)
            table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.tb.tb2")))
            rows = table.find_elements(By.TAG_NAME, "tr")
            data = []

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 4:
                    year_month = cols[0].text.strip()
                    monthly_revenue = cols[1].text.strip().replace(",", "")
                    mom_rate = cols[2].text.strip().replace("%", "")
                    if mom_rate == "--":
                        mom_rate = "0"
                    yoy_rate = cols[3].text.strip().replace("%", "")

                    if year_month.isdigit() and len(year_month) == 6:
                        try:
                            revenue_val = float(monthly_revenue)
                            mom_val = float(mom_rate)
                            yoy_val = float(yoy_rate)
                            data.append((stock_id, year_month, revenue_val, mom_val, yoy_val))
                        except ValueError:
                            continue

            driver.quit()
            return data
        except (TimeoutException, WebDriverException) as e:
            print(f"🔁 {stock_id} 嘗試第 {attempt+1} 次失敗：{e}")
            try:
                driver.quit()
            except:
                pass
            if attempt == MAX_RETRIES - 1:
                print(f"❌ {stock_id} 連續失敗，跳過")
                return []
        except Exception as e:
            print(f"❌ {stock_id} 發生例外錯誤: {e}")
            return []

def save_to_db(data, db_path="data/institution.db"):
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_revenue (
            stock_id TEXT,
            year_month TEXT,
            revenue REAL,
            mom_rate REAL,
            yoy_rate REAL,
            PRIMARY KEY (stock_id, year_month)
        )
    """)
    success_count = 0
    for row in data:
        cursor.execute("""
            INSERT OR IGNORE INTO monthly_revenue
            (stock_id, year_month, revenue, mom_rate, yoy_rate)
            VALUES (?, ?, ?, ?, ?)
        """, row)
        if cursor.rowcount > 0:
            success_count += 1

    conn.commit()
    conn.close()
    return success_count

if __name__ == "__main__":
    # 若加上 --schedule，才限制 6~14 號執行
    if "--schedule" in sys.argv:
        today = datetime.today()
        if today.day < 6 or today.day > 14:
            print("📅 今日非月營收公告期間（6~14 號），排程模式下不執行。")
            exit(0)

    # 若有傳入 txt 檔參數，使用該檔案；否則預設為 my_stock_holdings.txt
    stock_file = "my_stock_holdings.txt"
    for arg in sys.argv:
        if arg.endswith(".txt") and os.path.exists(arg):
            stock_file = arg
            break

    print(f"📄 使用的股票清單：{stock_file}")
    with open(stock_file, "r", encoding="utf-8") as f:
        stock_list = [line.strip() for line in f if line.strip()]

    for stock_id in stock_list:
        print(f"📥 抓取 {stock_id} 月營收資料...")
        records = fetch_monthly_revenue(stock_id)
        if records:
            print(f"📊 解析到 {len(records)} 筆資料")
            success = save_to_db(records)
            print(f"✅ 寫入 {success} 筆（未重複）")
        else:
            print(f"⏭️  {stock_id} 無資料或失敗")
    print("🎉 所有股票處理完畢")
