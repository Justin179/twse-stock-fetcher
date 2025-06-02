
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import sqlite3
import time
import os

# 股票代碼
stock_id = "3017"
url = f"https://www.cmoney.tw/finance/{stock_id}/f00036"

# DB 初始化
db_path = os.path.join("data", "institution.db")
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 啟動 headless 瀏覽器
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_experimental_option("prefs", {
    "profile.default_content_setting_values.notifications": 2
})
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(url)

# 捲動到底部觸發 lazy load
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(2)

# 等待 table 載入
wait = WebDriverWait(driver, 10)
table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.tb.tb1")))

# 擷取表格資料
rows = table.find_elements(By.TAG_NAME, "tr")
update_count = 0

for row in rows:
    cols = [td.text.strip().replace(",", "").replace("%", "") for td in row.find_elements(By.TAG_NAME, "td")]
    if cols and len(cols) >= 11 and cols[0] != "日期":
        try:
            # 日期轉換
            date = cols[0]
            if "/" in date:  # 民國轉西元
                parts = date.split("/")
                year = int(parts[0]) + 1911
                date = f"{year}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"

            # 欄位解析
            foreign_netbuy = int(cols[1])
            trust_netbuy = int(cols[2])
            foreign_shares = int(cols[5])
            foreign_ratio = float(cols[6])
            trust_shares = int(cols[7])
            trust_ratio = float(cols[8])

            # 更新或插入 DB
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
conn.commit()
conn.close()

print(f"✅ 已更新/寫入 {update_count} 筆資料")
