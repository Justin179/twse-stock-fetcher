import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import sqlite3
import time
import os
from datetime import datetime, timedelta

"""
手動的建立初始資料「專用」(每日法人買賣超與持股比率)(日期往回99日，含今，有67個交易日)，之後排程就能接手更新最後的5筆
讀取股票清單 →
逐一打開該股的網頁 →
設定查詢起始日 →
取得法人表格 →
抓資料逐筆解析 & 檢查是否已寫入 →
若尚未寫入 → 寫入 DB →
完成後繼續處理下一檔 →
全部完成 → 關閉 DB
"""
# 載入股票代碼清單 my_stock_holdings.txt
with open("temp_list.txt", "r", encoding="utf-8") as f:
    stock_list = [line.strip() for line in f if line.strip()]

# 設定 DB
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

# 處理每支股票
for stock_id in stock_list:
    print(f"🔍 處理股票 {stock_id} ...")
    try:
        end_date = datetime.today()
        start_date = end_date - timedelta(days=99)
        year_index = 1 if start_date.year == end_date.year else 0
        start_month = str(start_date.month)
        start_day = str(start_date.day)

        url = f"https://www.sinotrade.com.tw/Stock/Stock_3_1/Stock_3_1_6_4?ticker={stock_id}"

        # 啟動 headless 瀏覽器
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        iframe = wait.until(EC.presence_of_element_located((By.ID, "SysJustIFRAME")))
        driver.switch_to.frame(iframe)

        Select(driver.find_element(By.NAME, "Y2")).select_by_index(year_index)
        Select(driver.find_element(By.NAME, "M2")).select_by_value(start_month)
        Select(driver.find_element(By.NAME, "D2")).select_by_value(start_day)
        driver.find_element(By.NAME, "BB").click()

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.t01")))
        time.sleep(0.5)
        table = driver.find_element(By.CSS_SELECTOR, "table.t01")

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

        if insert_rows:
            cursor.executemany("""
                INSERT INTO institutional_netbuy_holding
                (stock_id, date, foreign_netbuy, trust_netbuy,
                foreign_shares, foreign_ratio, trust_shares, trust_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, insert_rows)
            conn.commit()
            print(f"✅ {stock_id} 補入 {len(insert_rows)} 筆新資料")
        else:
            print(f"⚠️ {stock_id} 無新資料")

    except Exception as e:
        print(f"🚨 錯誤：{stock_id} 解析失敗：{e}")

conn.close()
print("✅ 全部股票處理完畢")
