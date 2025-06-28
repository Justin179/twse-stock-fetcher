import sqlite3
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd

def fetch_twse_index(months_to_fetch=1):
    url = "https://www.twse.com.tw/zh/indices/taiex/mi-5min-hist.html"

    # 設定 Chrome 選項（不使用 headless，方便觀察畫面）
    options = Options()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(url)
        time.sleep(2)

        # 嘗試關閉聲明彈窗
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
            roc_year = year - 1911
            month = target_date.month
            print(f"\n🔁 抓取：{year} 年 {month} 月")

            # 選擇年份
            year_select = Select(wait.until(EC.presence_of_element_located((By.ID, "label0"))))
            year_select.select_by_value(str(year))
            time.sleep(0.5)

            # 選擇月份
            month_select = Select(wait.until(EC.presence_of_element_located((By.NAME, "mm"))))
            month_select.select_by_value(str(month))
            time.sleep(0.5)

            # 送出表單
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
                        all_data.append([
                            "^TWII",
                            cols[0],
                            round(float(cols[4]), 2),  # close
                            round(float(cols[2]), 2),  # high
                            round(float(cols[3]), 2),  # low
                            round(float(cols[1]), 2),  # open
                            0  # volume
                        ])
            except Exception as e:
                print(f"❌ 異常跳過：{year} 年 {month} 月，錯誤: {e}")
                continue

    finally:
        driver.quit()

    df = pd.DataFrame(all_data, columns=["stock_id", "date", "close", "high", "low", "open", "volume"])
    print("📋 抓取結果前幾筆：")
    print(df.head())

    if not df.empty:
        conn = sqlite3.connect("data/institution.db")
        table_name = "twse_prices"
        try:
            df.to_sql(table_name, conn, if_exists="append", index=False)
            print(f"✅ 共寫入 {len(df)} 筆資料")
        except sqlite3.IntegrityError as e:
            print(f"⚠️ 資料寫入失敗：{e}")
        finally:
            conn.close()
    else:
        print("⚠️ 無資料寫入")

if __name__ == "__main__":
    fetch_twse_index(months_to_fetch=3)
