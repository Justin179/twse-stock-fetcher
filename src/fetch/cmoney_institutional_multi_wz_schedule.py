import sys

import os
from datetime import datetime
"""
排程1: 更新每日外資與投信買賣超與持股比率資料
ON CONFLICT(stock_id, date) DO UPDATE SET
因為cmoney 一次就只有5筆資料，所以每天應會新增1筆，更新4筆
"""
# 建立 logs 資料夾
os.makedirs("logs", exist_ok=True)
log_path = os.path.join("logs", f"log_{datetime.today().strftime('%Y%m%d')}.txt")

# 將 print 同時輸出到 console 與 log 檔案
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open(log_path, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        pass

sys.stdout = Logger()
print(f"\n🕒 開始執行時間：{datetime.now()}")

from datetime import datetime

# 若以 --schedule 參數啟動，且今天是週六或週日，則退出
if "--schedule" in sys.argv:
    today = datetime.today()
    if today.weekday() >= 5:
        print("🛑 今天是週末，不執行排程。")
        exit(0)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import sqlite3
import time
import os

# 載入股票清單
with open("my_stock_holdings.txt", "r", encoding="utf-8") as f:
    stock_list = [line.strip() for line in f if line.strip()]

# DB 初始化
db_path = os.path.join("data", "institution.db")
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

MAX_RETRIES = 3
fail_reasons = []

for stock_id in stock_list:
    print(f"🔍 處理 {stock_id} ...")
    url = f"https://www.cmoney.tw/finance/{stock_id}/f00036"
    success = False

    for attempt in range(MAX_RETRIES):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2
            })
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)

            # 滾動觸發 lazy load
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            wait = WebDriverWait(driver, 10)
            table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.tb.tb1")))
            rows = table.find_elements(By.TAG_NAME, "tr")
            update_count = 0
            invalid_row_found = False

            for row in rows:
                cols = [td.text.strip().replace(",", "").replace("%", "") for td in row.find_elements(By.TAG_NAME, "td")]
                if cols and len(cols) >= 11 and cols[0] != "日期":
                    try:
                        if any(not cols[i] for i in [1,2,5,6,7,8]):
                            print(f"⚠️ 資料遺漏於 {cols[0]}，跳過整支 {stock_id}")
                            fail_reasons.append((stock_id, "資料遺漏"))
                            invalid_row_found = True
                            break

                        date = cols[0]
                        if "/" in date:
                            parts = date.split("/")
                            year = int(parts[0]) + 1911
                            date = f"{year}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"

                        foreign_netbuy = int(cols[1])
                        trust_netbuy = int(cols[2])
                        foreign_shares = int(cols[5])
                        foreign_ratio = float(cols[6])
                        trust_shares = int(cols[7])
                        trust_ratio = float(cols[8])

                        cursor.execute("""
                            INSERT INTO institutional_netbuy_holding
                            (stock_id, date, foreign_netbuy, trust_netbuy,
                             foreign_shares, foreign_ratio, trust_shares, trust_ratio)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(stock_id, date) DO UPDATE SET
                                foreign_netbuy=excluded.foreign_netbuy,
                                trust_netbuy=excluded.trust_netbuy,
                                foreign_shares=excluded.foreign_shares,
                                foreign_ratio=excluded.foreign_ratio,
                                trust_shares=excluded.trust_shares,
                                trust_ratio=excluded.trust_ratio
                        """, (stock_id, date, foreign_netbuy, trust_netbuy,
                              foreign_shares, foreign_ratio, trust_shares, trust_ratio))
                        update_count += 1
                    except Exception as e:
                        print(f"❌ 錯誤於 {cols[0]}: {e}")

            driver.quit()

            if not invalid_row_found:
                conn.commit()
                print(f"✅ {stock_id} 寫入或更新 {update_count} 筆")
            success = True
            break

        except (TimeoutException, WebDriverException) as e:
            print(f"⚠️ 嘗試 {attempt+1}/{MAX_RETRIES} 失敗：{e}")
            try:
                driver.quit()
            except:
                pass
            if attempt == MAX_RETRIES - 1:
                print(f"🚨 {stock_id} 因連線失敗無法處理，略過")
                fail_reasons.append((stock_id, "連線失敗"))
        except Exception as e:
            print(f"❌ 其他錯誤：{e}")
            fail_reasons.append((stock_id, "其他錯誤"))
            break

conn.close()

# 輸出未更新股票與原因
if fail_reasons:
    print("\n❗ 未更新股票列表：")
    for sid, reason in fail_reasons:
        print(f"🚫 {sid} - {reason}")
else:
    print("🎉 所有股票皆成功寫入")

