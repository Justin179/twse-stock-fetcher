# src/fetch/fetch_index_otc_tpex_to_db.py

import os
import time
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd


def convert_date(minguo_date_str):
    """將民國年月日轉為西元日期字串"""
    y, m, d = minguo_date_str.split('/')
    year = int(y) + 1911
    return f"{year}-{int(m):02d}-{int(d):02d}"


def fetch_otc_index():
    url = "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/daily-indices.html"

    options = webdriver.ChromeOptions()
    # 不啟用 headless，測試階段會看到操作
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)

    time.sleep(3)  # 等待 JavaScript 載入

    # 解析表格
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    data = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 6:
            continue

        raw_date = cols[0].text.strip()
        raw_volume = cols[1].text.replace(",", "").strip()
        raw_index = cols[4].text.strip()

        try:
            date = convert_date(raw_date)
            volume = int(raw_volume)
            close = float(raw_index)

            data.append({
                "stock_id": "^OTCI",
                "date": date,
                "volume": volume,
                "close": round(close, 2)
            })
        except Exception as e:
            print(f"⚠️ 跳過資料列（{raw_date}）: {e}")

    driver.quit()
    return pd.DataFrame(data)


def save_to_db(df, db_path="data/institution.db"):
    abs_path = os.path.abspath(db_path)
    print(f"📁 DB 實際寫入路徑：{abs_path}")

    conn = sqlite3.connect(abs_path)
    cursor = conn.cursor()
    success_count = 0

    for count, (_, row) in enumerate(df.iterrows(), 1):
        try:
            stock_id = str(row["stock_id"])
            date = row["date"]
            close = row["close"]
            volume = row["volume"]

            cursor.execute(
                """
                INSERT OR IGNORE INTO twse_prices (stock_id, date, close, volume)
                VALUES (?, ?, ?, ?)
                """,
                (stock_id, date, close, volume)
            )

            if cursor.rowcount > 0:
                success_count += 1
        except Exception as e:
            print(f"⚠️ 第 {count} 筆寫入失敗: {e}")

    conn.commit()
    print(f"✅ 成功寫入 {success_count} 筆")
    conn.close()


if __name__ == "__main__":
    df = fetch_otc_index()
    print(df.head())
    save_to_db(df)
