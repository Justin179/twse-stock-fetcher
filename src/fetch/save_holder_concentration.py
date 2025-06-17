import sqlite3
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

"""
排程2: 更新每週 籌碼集中度 與 千張大戶持股比率
INSERT OR IGNORE INTO holder_concentration
爬蟲資料很多的神秘金字塔
"""
def fetch_holder_concentration_selenium(stock_id: str):
    url = f"https://norway.twsthr.info/StockHolders.aspx?stock={stock_id}"

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)

    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    table = soup.find("table", id="Details")
    if not table:
        print(f"\u274c 找不到資料表格 for {stock_id}")
        return []

    rows = table.find_all("tr")
    print(f"\u2705 共找到 {len(rows)} 列 tr")

    data = []
    for i, row in enumerate(rows):
        cols = row.find_all("td")
        if len(cols) >= 15:
            date = cols[2].text.strip().replace("/", "")
            avg_shares = cols[5].text.strip().replace(",", "")
            ratio_1000 = cols[13].text.strip()
            close_price = cols[14].text.strip()

            if date.isdigit() and len(date) == 8:
                data.append((stock_id, date, avg_shares, ratio_1000, close_price))

    if not data:
        print("\u274c 表格抓到但沒有有效資料列")
    return data


if __name__ == "__main__":
    db_path = Path("data/institution.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 創表 (if not exists)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS holder_concentration (
            stock_id TEXT,
            date TEXT,
            avg_shares REAL,
            ratio_1000 REAL,
            close_price REAL,
            PRIMARY KEY (stock_id, date)
        )
    """)

    with open("my_stock_holdings.txt", "r", encoding="utf-8") as f:
        stock_list = [line.strip() for line in f if line.strip()]

    for stock_id in stock_list:
        print(f"\n\U0001f50d 正在處理股票: {stock_id}...")
        try:
            records = fetch_holder_concentration_selenium(stock_id)
        except Exception as e:
            print(f"\u274c 發生錯誤: {e}")
            continue

        success = 0
        for row in records:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO holder_concentration 
                    (stock_id, date, avg_shares, ratio_1000, close_price)
                    VALUES (?, ?, ?, ?, ?)
                """, row)
                if cursor.rowcount > 0:
                    success += 1
            except Exception as e:
                print(f"\u274c insert error: {e}")

        conn.commit()
        print(f"\u2705 新增 {success} 筆資料")

        # ✅ 若 1101 無新增筆數，直接中斷程式
        if stock_id == "1101" and success == 0:
            print("⛔️ 1101 無新增資料(視為還沒有新的資料)，已中止後續處理")
            break

    conn.close()
    print("\n\U0001f389 全部完成")