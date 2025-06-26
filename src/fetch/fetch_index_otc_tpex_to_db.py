import os
import time
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd


def convert_date(minguo_date_str):
    y, m, d = minguo_date_str.split('/')
    year = int(y) + 1911
    return f"{year}-{int(m):02d}-{int(d):02d}"


def fetch_otc_index(months=1):
    url = "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/daily-indices.html"

    options = webdriver.ChromeOptions()
    # 測試階段顯示瀏覽器
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(3)

    # 日期選擇器
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

        # 選擇年份與月份
        select_year.select_by_visible_text(year_str)
        select_month.select_by_value(month_str)

        time.sleep(3)

        # 抓取表格資料
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
            cursor.execute(
                """
                INSERT OR IGNORE INTO twse_prices (stock_id, date, close, volume)
                VALUES (?, ?, ?, ?)
                """,
                (row["stock_id"], row["date"], row["close"], row["volume"])
            )
            if cursor.rowcount > 0:
                success_count += 1
        except Exception as e:
            print(f"⚠️ 第 {count} 筆寫入失敗: {e}")

    conn.commit()
    print(f"✅ 寫入成功筆數: {success_count}")
    conn.close()


if __name__ == "__main__":
    # 設為 69 抓取過去 69 個月（含當月），平時日更改為 1
    months_to_fetch = 69
    df = fetch_otc_index(months=months_to_fetch)
    print(df.head())
    save_to_db(df)
