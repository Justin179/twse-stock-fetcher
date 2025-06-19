import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import sqlite3
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

MAX_RETRIES = 3

def fetch_profitability_from_histock(stock_id):
    url = f"https://histock.tw/stock/{stock_id}/%E5%88%A9%E6%BD%A4%E6%AF%94%E7%8E%87"

    for attempt in range(MAX_RETRIES):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)
            time.sleep(3)

            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'tbBasic')]//tr")))
            table = driver.find_element(By.XPATH, "//table[contains(@class, 'tbBasic')]")
            print("✅ 已正確取得 table，開始解析")

            rows = table.find_elements(By.TAG_NAME, "tr")
            print(f"共找到 {len(rows)} 列")

            data = []
            for row in rows[1:]:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 5:
                    season = cols[0].text.strip()
                    try:
                        gross = float(cols[1].text.strip().replace('%', ''))
                        operating = float(cols[2].text.strip().replace('%', ''))
                        net = float(cols[4].text.strip().replace('%', ''))
                        data.append((stock_id, season, gross, operating, net))
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
        CREATE TABLE IF NOT EXISTS profitability_ratios (
            stock_id TEXT,
            season TEXT,
            gross_profit_margin REAL,
            operating_profit_margin REAL,
            net_income_margin REAL,
            PRIMARY KEY (stock_id, season)
        )
    """)
    success_count = 0
    for row in data:
        cursor.execute("""
            INSERT OR IGNORE INTO profitability_ratios
            (stock_id, season, gross_profit_margin, operating_profit_margin, net_income_margin)
            VALUES (?, ?, ?, ?, ?)
        """, row)
        if cursor.rowcount > 0:
            success_count += 1

    conn.commit()
    conn.close()
    return success_count

if __name__ == "__main__":
    stock_list = ["3017"]  # 僅測試單一個股

    for stock_id in stock_list:
        print(f"📥 抓取 {stock_id} 財報三率（HiStock）...")
        records = fetch_profitability_from_histock(stock_id)
        if records:
            print(f"📊 解析到 {len(records)} 筆資料")
            success = save_to_db(records)
            print(f"✅ 寫入 {success} 筆（未重複）")
        else:
            print(f"⏭️  {stock_id} 無資料或失敗")

    print("🎉 所有股票處理完畢")
