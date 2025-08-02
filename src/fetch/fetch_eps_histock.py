# fetch_eps_histock_test.py
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
DB_PATH = "data/institution.db"
TEST_STOCK_ID = "2330"  # 測試用股票代碼

# --------------------------------------------------------
# 抓取 HiStock EPS
# --------------------------------------------------------
def fetch_eps_from_histock(stock_id):
    url = f"https://histock.tw/stock/{stock_id}/%E6%AF%8F%E8%82%A1%E7%9B%88%E9%A4%98"

    for attempt in range(MAX_RETRIES):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)
            time.sleep(3)

            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'tbBasic')]//tr")))
            table = driver.find_element(By.XPATH, "//table[contains(@class, 'tbBasic')]")
            print(f"✅ {stock_id} EPS 表格載入成功")

            # 印出整個表格 HTML
            print("=== 抓到的表格 HTML ===")
            print(table.get_attribute("outerHTML"))
            print("=======================")

            rows = table.find_elements(By.TAG_NAME, "tr")

            # 第一列是年份
            header_cells = rows[0].find_elements(By.TAG_NAME, "th")
            years = [cell.text.strip() for cell in header_cells[1:]]  # 跳過第一欄「季別/年度」

            data = []
            for row in rows[1:]:
                cols = row.find_elements(By.TAG_NAME, "td")
                if not cols:
                    continue
                quarter = cols[0].text.strip()
                if quarter.upper() not in ["Q1", "Q2", "Q3", "Q4"]:
                    continue  # 跳過總計
                for i, year in enumerate(years):
                    try:
                        eps_value = float(cols[i+1].text.strip())
                        season_label = f"{year}{quarter}"
                        data.append((stock_id, season_label, eps_value))
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

# --------------------------------------------------------
# 寫入 SQLite
# --------------------------------------------------------
def save_eps_to_db(data, db_path="data/institution.db"):
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 確保 eps 欄位存在
    cursor.execute("PRAGMA table_info(profitability_ratios)")
    columns = [col[1] for col in cursor.fetchall()]
    if "eps" not in columns:
        cursor.execute("ALTER TABLE profitability_ratios ADD COLUMN eps REAL")
        print("✅ 已新增 eps 欄位")

    success_count = 0
    for stock_id, season, eps_value in data:
        # 先檢查該複合主鍵是否存在
        cursor.execute("""
            SELECT 1 FROM profitability_ratios
            WHERE stock_id = ? AND season = ?
        """, (stock_id, season))
        if cursor.fetchone():  # 存在才更新
            cursor.execute("""
                UPDATE profitability_ratios
                SET eps = ?
                WHERE stock_id = ? AND season = ?
            """, (eps_value, stock_id, season))
            if cursor.rowcount > 0:
                success_count += 1

    conn.commit()
    conn.close()
    return success_count


# --------------------------------------------------------
# 主程式
# --------------------------------------------------------
if __name__ == "__main__":
    print(f"📥 抓取 {TEST_STOCK_ID} EPS（HiStock 測試版）...")
    eps_records = fetch_eps_from_histock(TEST_STOCK_ID)
    if eps_records:
        print(f"📊 解析到 {len(eps_records)} 筆 EPS 資料")
        success = save_eps_to_db(eps_records)
        print(f"✅ 寫入 {success} 筆（包含更新）")
    else:
        print(f"⏭️  {TEST_STOCK_ID} 無 EPS 資料或失敗")

    print("🎉 測試完成")
