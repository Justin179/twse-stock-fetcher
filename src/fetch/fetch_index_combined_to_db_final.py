
# src/fetch/fetch_index_combined_to_db.py

import os
import time
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def fetch_twii_index():
    today = datetime.today()
    start_date = (today - relativedelta(months=1)).strftime('%Y-%m-%d')  # 抓取近一個月資料
    end_date = today.strftime('%Y-%m-%d')

    df = yf.download("^TWII", start=start_date, end=end_date, progress=False)
    if df.empty:
        print("❌ 沒有抓到 TWS (^TWII) 的資料")
        return pd.DataFrame()

    df = df.reset_index()
    df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    df['stock_id'] = '^TWII'

    return df[['stock_id', 'date', 'open', 'high', 'low', 'close', 'volume']]


def convert_date(minguo_date_str):
    y, m, d = minguo_date_str.split('/')
    year = int(y) + 1911
    return f"{year}-{int(m):02d}-{int(d):02d}"


def fetch_otci_index(months=1):
    url = "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/daily-indices.html"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(3)

    select_year = Select(driver.find_element(By.CSS_SELECTOR, "select.select-year"))
    select_month = Select(driver.find_element(By.CSS_SELECTOR, "select.select-month"))

    today = datetime.today()
    all_data = []

    for i in range(months):
        target_date = today - relativedelta(months=i)
        minguo_year = target_date.year - 1911
        year_str = f"{minguo_year}年"
        month_str = str(target_date.month)

        print(f"🔁 抓取：{year_str}{month_str}月")

        select_year.select_by_visible_text(year_str)
        select_month.select_by_value(month_str)

        time.sleep(3)

        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 6:
                continue

            try:
                date = convert_date(cols[0].text.strip())
                volume = int(cols[1].text.replace(",", "").strip())
                close = round(float(cols[4].text.strip()), 2)

                all_data.append({
                    "stock_id": "^OTCI",
                    "date": date,
                    "volume": volume,
                    "close": close
                })
            except Exception as e:
                print(f"⚠️ 資料錯誤跳過: {e}")

    driver.quit()
    return pd.DataFrame(all_data)


def save_to_db(df, db_path="data/institution.db"):
    abs_path = os.path.abspath(db_path)
    print(f"📁 DB 實際寫入路徑：{abs_path}")

    conn = sqlite3.connect(abs_path)
    cursor = conn.cursor()
    success_count = 0

    for count, (_, row) in enumerate(df.iterrows(), 1):
        try:
            stock_id = str(row["stock_id"])
            date_obj = row["date"]
            if pd.isna(date_obj):
                raise ValueError("❌ 日期是 NaT")

            date = pd.to_datetime(date_obj).strftime('%Y-%m-%d')

            close = round(float(row["close"]), 2)
            volume = int(row["volume"])

            open_ = high = low = None
            if "open" in row and not pd.isna(row["open"]):
                open_ = round(float(row["open"]), 2)
            if "high" in row and not pd.isna(row["high"]):
                high = round(float(row["high"]), 2)
            if "low" in row and not pd.isna(row["low"]):
                low = round(float(row["low"]), 2)

            cursor.execute(
                """
                INSERT OR IGNORE INTO twse_prices (stock_id, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (stock_id, date, open_, high, low, close, volume)
            )

            if cursor.rowcount > 0:
                success_count += 1
        except Exception as e:
            print(f"⚠️ 第 {count} 筆寫入失敗: {e}")

    conn.commit()
    print(f"✅ 寫入成功筆數: {success_count}")
    conn.close()


if __name__ == "__main__":
    df_twii = fetch_twii_index()
    df_otci = fetch_otci_index(months=1)
    df_all = pd.concat([df_twii, df_otci], ignore_index=True)
    print(df_all.head())
    save_to_db(df_all)
