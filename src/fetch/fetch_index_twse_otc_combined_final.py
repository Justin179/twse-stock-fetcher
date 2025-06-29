
import os
import time
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ====== 上市指數抓取 ======
def fetch_twse_index(months_to_fetch=1):
    def convert_roc_to_ad(roc_date_str):
        try:
            roc_year, month, day = map(int, roc_date_str.split("/"))
            ad_year = roc_year + 1911
            return f"{ad_year}-{month:02d}-{day:02d}"
        except:
            return None

    url = "https://www.twse.com.tw/zh/indices/taiex/mi-5min-hist.html"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    all_data = []
    try:
        driver.get(url)
        time.sleep(2)
        try:
            close_btn = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "close")))
            close_btn.click()
            print("✅ TWSE: 關閉聲明視窗")
        except Exception as e:
            print(f"⚠️ TWSE: 無法關閉聲明視窗: {e}")

        today = datetime.today()
        for i in range(months_to_fetch):
            target_date = today.replace(day=1) - timedelta(days=30 * i)
            year, month = target_date.year, target_date.month
            print(f"🔁 TWSE 抓取：{year} 年 {month} 月")
            Select(wait.until(EC.presence_of_element_located((By.ID, "label0")))).select_by_value(str(year))
            Select(wait.until(EC.presence_of_element_located((By.NAME, "mm")))).select_by_value(str(month))
            time.sleep(0.5)
            driver.find_element(By.ID, "form").submit()
            time.sleep(1)
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            for row in rows:
                cols = [td.text.strip().replace(",", "") for td in row.find_elements(By.TAG_NAME, "td")]
                if len(cols) >= 5:
                    ad_date = convert_roc_to_ad(cols[0].replace("-", "/"))
                    if ad_date:
                        all_data.append(["^TWII", ad_date, round(float(cols[4]), 2), None, None, None, None])
    finally:
        driver.quit()

    df = pd.DataFrame(all_data, columns=["stock_id", "date", "close", "high", "low", "open", "volume"])
    save_to_db(df, "TWSE")


# ====== 上櫃指數抓取 ======
def fetch_otc_index(months=1):
    def convert_date(minguo_date_str):
        y, m, d = minguo_date_str.split('/')
        year = int(y) + 1911
        return f"{year}-{int(m):02d}-{int(d):02d}"

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
        year_str = f"{target_date.year - 1911}年"
        month_str = str(target_date.month)
        print(f"🔁 OTC 抓取：{year_str}{month_str}月")
        select_year.select_by_visible_text(year_str)
        select_month.select_by_value(month_str)
        time.sleep(3)
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 6:
                try:
                    date = convert_date(cols[0].text.strip())
                    volume = int(cols[1].text.replace(",", "").strip())
                    close = round(float(cols[4].text.strip()), 2)
                    all_data.append(["^OTCI", date, close, None, None, None, volume])
                except:
                    continue
    driver.quit()

    df = pd.DataFrame(all_data, columns=["stock_id", "date", "close", "high", "low", "open", "volume"])
    save_to_db(df, "OTC")


# ====== 寫入資料庫 ======
def save_to_db(df, label):
    if df.empty:
        print(f"⚠️ {label} 無資料寫入")
        return
    conn = sqlite3.connect("data/institution.db")
    cursor = conn.cursor()
    inserted = 0
    for _, row in df.iterrows():
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO twse_prices (stock_id, date, close, high, low, open, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                tuple(row)
            )
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"⚠️ {label} 寫入失敗: {e}")
    conn.commit()
    conn.close()
    print(f"✅ {label} 成功寫入 {inserted} 筆")


if __name__ == "__main__":
    months_to_fetch = 1
    fetch_twse_index(months_to_fetch)
    fetch_otc_index(months_to_fetch)
