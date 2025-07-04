import os
import sys
import time
import sqlite3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB_PATH = "data/institution.db"
MAX_RETRY = 3

def fetch_main_force(stock_id):
    url = f"https://www.cmoney.tw/forum/stock/{stock_id}?s=main-force"

    for attempt in range(MAX_RETRY):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)
            wait = WebDriverWait(driver, 10)

            while True:
                try:
                    btn = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "//div[contains(@class, 'showMore__text') and contains(text(), '查看更多')]")
                    ))
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except:
                    break  # 無查看更多按鈕

            rows = driver.find_elements(By.CSS_SELECTOR, "div.table__border tbody tr")
            data = []
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 4:
                    date = cols[0].text.strip()
                    close_price = cols[1].text.replace(",", "")
                    net_buy_sell = cols[2].text.replace(",", "")
                    dealer_diff = cols[3].text.replace(",", "")
                    try:
                        data.append((
                            stock_id,
                            date,
                            float(close_price),
                            int(net_buy_sell),
                            int(dealer_diff)
                        ))
                    except ValueError:
                        continue

            driver.quit()
            return data

        except (WebDriverException, TimeoutException) as e:
            print(f"⚠️  {stock_id} 第 {attempt+1} 次抓取失敗：{e}")
            try:
                driver.quit()
            except:
                pass
            if attempt == MAX_RETRY - 1:
                print(f"❌ {stock_id} 重試失敗，跳過")
                return []
        except Exception as e:
            print(f"❌ {stock_id} 發生例外錯誤：{e}")
            return []

def save_to_db(data, db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS main_force_trading (
            stock_id TEXT,
            date TEXT,
            close_price REAL,
            net_buy_sell INTEGER,
            dealer_diff INTEGER,
            PRIMARY KEY (stock_id, date)
        )
    """)

    success = 0
    for row in data:
        cursor.execute("""
            INSERT OR IGNORE INTO main_force_trading
            (stock_id, date, close_price, net_buy_sell, dealer_diff)
            VALUES (?, ?, ?, ?, ?)
        """, row)
        if cursor.rowcount > 0:
            success += 1

    conn.commit()
    conn.close()
    return success

if __name__ == "__main__":
    # 判斷是否有傳入 txt 清單檔
    stock_file = "my_stock_holdings.txt"
    for arg in sys.argv[1:]:
        if arg.endswith(".txt") and os.path.exists(arg):
            stock_file = arg
            break

    print(f"📄 使用股票清單：{stock_file}")
    with open(stock_file, "r", encoding="utf-8") as f:
        stock_list = [line.strip() for line in f if line.strip()]

    for stock_id in stock_list:
        print(f"📥 抓取 {stock_id} 主力進出資料中...")
        records = fetch_main_force(stock_id)
        if records:
            inserted = save_to_db(records)
            print(f"✅ {stock_id} 新增 {inserted} 筆資料（不含重複）")
        else:
            print(f"⏭️  {stock_id} 無資料或全部重試失敗")

    print("🎉 全部處理完畢")
