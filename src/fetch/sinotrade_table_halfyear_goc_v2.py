
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import os

# 股票代碼與起始月（年份用 index 控制）
stock_id = "3017"
year_index = 0  # 0=去年, 1=今年
start_month = "10"  # 民國月（01~12）

# URL
url = f"https://www.sinotrade.com.tw/Stock/Stock_3_1/Stock_3_1_6_4?ticker={stock_id}"

# output 資料夾
output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "output")
os.makedirs(output_dir, exist_ok=True)

# 啟動瀏覽器
options = webdriver.ChromeOptions()
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(url)
wait = WebDriverWait(driver, 10)

# 切入 iframe
iframe = wait.until(EC.presence_of_element_located((By.ID, "SysJustIFRAME")))
driver.switch_to.frame(iframe)

# 年用 index，月用 value 選擇起始日期
Select(driver.find_element(By.NAME, "Y2")).select_by_index(year_index)
Select(driver.find_element(By.NAME, "M2")).select_by_value(start_month)

# 點擊查詢按鈕 (name=BB)
search_btn = driver.find_element(By.NAME, "BB")
search_btn.click()

# 等待資料表格出現
wait = WebDriverWait(driver, 20)
table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.t01")))

# 擷取資料
rows = table.find_elements(By.TAG_NAME, "tr")
data = []
for row in rows:
    cols = [td.text.strip() for td in row.find_elements(By.TAG_NAME, "td")]
    if len(cols) == 11 and not "合計" in cols[0]:
        data.append(cols)

driver.quit()

# 欄位名稱
columns = ["日期", "外資買賣超", "投信買賣超", "自營商買賣超", "三大法人買賣超",
           "外資持股張數", "投信持股張數", "自營商持股張數",
           "外資持股比率", "投信持股比率", "三大法人持股比率"]

# 輸出 CSV
df = pd.DataFrame(data, columns=columns)
csv_path = os.path.join(output_dir, f"sinotrade_goc_v2_{stock_id}_Y{year_index}_M{start_month}.csv")
df.to_csv(csv_path, index=False, encoding="utf-8-sig")
print(df)
