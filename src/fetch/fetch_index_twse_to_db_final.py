import sqlite3
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd

def convert_roc_to_ad(roc_date_str):
    """將民國日期字串 (例如 114/06/27) 轉為西元日期 (2025-06-27)"""
    try:
        roc_year, month, day = map(int, roc_date_str.split("/"))
        ad_year = roc_year + 1911
        return f"{ad_year}-{month:02d}-{day:02d}"
    except:
        return None

def fetch_twse_index(months_to_fetch=1):
    url = "https://www.twse.com.tw/zh/indices/taiex/mi-5min-hist.html"

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(url)
        time.sleep(2)

        try:
            close_btn = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "close")))
            close_btn.click()
            print("✅ 成功關閉聲明視窗")
        except Exception as e:
            print(f"⚠️ 無法關閉聲明彈窗: {e}")

        today = datetime.today()
        all_data = []

        for i in range(months_to_fetch):
            target_date = today.replace(day=1) - timedelta(days=30 * i)
            year = target_date.year
            month = target_date.month
            print(f"\n🔁 抓取：{year} 年 {month} 月")

            Select(wait.until(EC.presence_of_element_located((By.ID, "label0")))).select_by_value(str(year))
            Select(wait.until(EC.presence_of_element_located((By.NAME, "mm")))).select_by_value(str(month))
            time.sleep(0.5)

            try:
                form = driver.find_element(By.ID, "form")
                form.submit()
                print("✅ 直接 submit 表單，等待資料載入中...")
            except Exception as e:
                print(f"❌ 查詢按鈕點擊失敗: {e}")
                continue

            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
                time.sleep(1)
                rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                for row in rows:
                    cols = [td.text.strip().replace(",", "") for td in row.find_elements(By.TAG_NAME, "td")]
                    if len(cols) >= 5:
                        ad_date = convert_roc_to_ad(cols[0].replace("-", "/"))
                        if ad_date:
                            all_data.append([
                                "^TWII",
                                ad_date,
                                round(float(cols[4]), 2),  # close
                                None,  # high
                                None,  # low
                                None,  # open
                                None  # volume
                            ])
            except Exception as e:
                print(f"❌ 異常跳過：{year} 年 {month} 月，錯誤: {e}")
                continue

    finally:
        driver.quit()

    df = pd.DataFrame(all_data, columns=["stock_id", "date", "close", "high", "low", "open", "volume"])

    if not df.empty:
        conn = sqlite3.connect("data/institution.db")
        cursor = conn.cursor()
        table_name = "twse_prices"
        inserted_count = 0

        for _, row in df.iterrows():
            try:
                cursor.execute(f"""
                    INSERT OR IGNORE INTO {table_name} (stock_id, date, close, high, low, open, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, tuple(row))
                if cursor.rowcount > 0:
                    inserted_count += 1
            except Exception as e:
                print(f"⚠️ 無法寫入資料: {row['date']}，錯誤: {e}")


        conn.commit()
        conn.close()
        print(f"✅ 共寫入或更新 {inserted_count} 筆資料")
    else:
        print("⚠️ 無資料寫入")

if __name__ == "__main__":
    fetch_twse_index(months_to_fetch=1) # 設為 1 抓取當月資料
