import os
import time
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd

def convert_date(minguo_date_str):
    y, m, d = minguo_date_str.split('/')
    year = int(y) + 1911
    return f"{year}-{int(m):02d}-{int(d):02d}"

def fetch_twse_index():
    url = "https://www.twse.com.tw/zh/indices/taiex/mi-5min-hist.html"

    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # 可啟用無頭模式
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(2)

    # ✅ 自動關閉聲明彈窗（若有）
    try:
        print("🕵️ 嘗試關閉聲明彈窗...")
        agree_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#popupStatement .ok"))
        )
        agree_btn.click()
        print("✅ 成功關閉聲明視窗")
        time.sleep(1)
    except:
        print("ℹ️ 沒有出現彈窗，繼續執行")

    # 年月選擇
    year_select = Select(driver.find_element(By.NAME, "yy"))
    month_select = Select(driver.find_element(By.NAME, "mm"))
    year_select.select_by_visible_text("民國 114 年")
    month_select.select_by_value("6")  # 不補零

    # 查詢
    submit_button = driver.find_element(By.CLASS_NAME, "submit")
    driver.execute_script("arguments[0].click();", submit_button)
    time.sleep(3)

    # 抓資料
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    result = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 5:
            continue
        try:
            date = convert_date(cols[0].text.strip())
            close = round(float(cols[4].text.replace(",", "").strip()), 2)
            result.append({
                "date": date,
                "close": close,
                "stock_id": "^TWII"
            })
        except Exception as e:
            print(f"⚠️ 資料錯誤跳過: {e}")

    driver.quit()
    return pd.DataFrame(result)

def save_to_db(df, db_path="data/institution.db"):
    abs_path = os.path.abspath(db_path)
    print(f"📁 DB 實際寫入路徑：{abs_path}")

    conn = sqlite3.connect(abs_path)
    cursor = conn.cursor()
    success_count = 0

    for count, (_, row) in enumerate(df.iterrows(), 1):
        try:
            cursor.execute(
                """
                UPDATE twse_prices
                SET close = ?
                WHERE stock_id = ? AND date = ?
                """,
                (row["close"], row["stock_id"], row["date"])
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    INSERT INTO twse_prices (stock_id, date, close)
                    VALUES (?, ?, ?)
                    """,
                    (row["stock_id"], row["date"], row["close"])
                )
            success_count += 1
        except Exception as e:
            print(f"⚠️ 第 {count} 筆寫入失敗: {e}")

    conn.commit()
    print(f"✅ 寫入成功筆數: {success_count}")
    conn.close()

if __name__ == "__main__":
    df = fetch_twse_index()
    print(df.head())
    save_to_db(df)
