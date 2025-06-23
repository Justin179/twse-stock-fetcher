import os
import time
import sqlite3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

DB_PATH = "data/institution.db"

def fetch_main_force(stock_id):
    url = f"https://www.cmoney.tw/forum/stock/{stock_id}?s=main-force"
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new")  # 測試階段開視窗
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    wait = WebDriverWait(driver, 10)

    # 一直點擊「查看更多」
    while True:
        try:
            btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class, 'showMore__text') and contains(text(), '查看更多')]")
            ))
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
        except:
            break

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

    print(f"📄 共擷取 {len(data)} 筆")
    time.sleep(5)  # 可視化測試觀察時間
    driver.quit()
    return data

def save_to_db(data, db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ✅ 建立資料表（若不存在）
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
    stock_id = "2330"
    print(f"📥 抓取 {stock_id} 主力進出資料...")
    records = fetch_main_force(stock_id)
    inserted = save_to_db(records)
    print(f"✅ 新增 {inserted} 筆資料（不含重複）")
