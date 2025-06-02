
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import sqlite3
import time
import os

# 股票代碼與起始日期設定
stock_id = "3017"
year_index = 1
start_month = "3"
start_day = "1"

url = f"https://www.sinotrade.com.tw/Stock/Stock_3_1/Stock_3_1_6_4?ticker={stock_id}"

# 建立 SQLite 連線
db_path = os.path.join("data", "institution.db")
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 建立資料表
cursor.execute("""
CREATE TABLE IF NOT EXISTS institutional_netbuy_holding (
    stock_id TEXT NOT NULL,
    date TEXT NOT NULL,
    foreign_netbuy INTEGER,
    trust_netbuy INTEGER,
    foreign_shares INTEGER,
    foreign_ratio REAL,
    trust_shares INTEGER,
    trust_ratio REAL,
    PRIMARY KEY (stock_id, date)
)
""")
conn.commit()

# 啟動 Headless Chrome
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(url)
wait = WebDriverWait(driver, 10)

# 切入 iframe
iframe = wait.until(EC.presence_of_element_located((By.ID, "SysJustIFRAME")))
driver.switch_to.frame(iframe)

# 設定查詢日期
Select(driver.find_element(By.NAME, "Y2")).select_by_index(year_index)
Select(driver.find_element(By.NAME, "M2")).select_by_value(start_month)
Select(driver.find_element(By.NAME, "D2")).select_by_value(start_day)
driver.find_element(By.NAME, "BB").click()

# 等待並重新抓取新的 table 元素（避免 stale element）
wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.t01")))
time.sleep(0.5)
table = driver.find_element(By.CSS_SELECTOR, "table.t01")

# 擷取與轉換資料（最多重試兩次）
insert_rows = []
for attempt in range(2):
    try:
        rows = table.find_elements(By.TAG_NAME, "tr")
        for row in rows:
            cols = [td.text.strip().replace(",", "") for td in row.find_elements(By.TAG_NAME, "td")]
            if len(cols) == 11 and cols[0] != "日期" and not "合計" in cols[0]:
                try:
                    roc_parts = cols[0].split("/")
                    year = int(roc_parts[0]) + 1911
                    date = f"{year}-{roc_parts[1].zfill(2)}-{roc_parts[2].zfill(2)}"

                    # 若資料已存在則跳過
                    cursor.execute("SELECT 1 FROM institutional_netbuy_holding WHERE stock_id=? AND date=?", (stock_id, date))
                    if cursor.fetchone():
                        continue

                    foreign_netbuy = int(cols[1])
                    trust_netbuy = int(cols[2])
                    foreign_shares = int(cols[5])
                    trust_shares = int(cols[6])
                    foreign_ratio = float(cols[9].replace("%", ""))
                    total_shares = foreign_shares / (foreign_ratio / 100)
                    trust_ratio = round((trust_shares / total_shares) * 100, 2)

                    insert_rows.append((stock_id, date, foreign_netbuy, trust_netbuy,
                                        foreign_shares, foreign_ratio, trust_shares, trust_ratio))
                except Exception as e:
                    print(f"❌ 資料處理錯誤於 {cols[0]}: {e}")
        break
    except Exception as e:
        print(f"⚠️ 表格解析失敗，重試中 ({attempt + 1}/2)...")
        time.sleep(1)
        table = driver.find_element(By.CSS_SELECTOR, "table.t01")

driver.quit()

# 僅針對不存在的資料進行 INSERT
cursor.executemany(
    """
    INSERT INTO institutional_netbuy_holding
    (stock_id, date, foreign_netbuy, trust_netbuy,
     foreign_shares, foreign_ratio, trust_shares, trust_ratio)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, insert_rows
)
conn.commit()
conn.close()

print(f"✅ 已補入 {len(insert_rows)} 筆新資料")
