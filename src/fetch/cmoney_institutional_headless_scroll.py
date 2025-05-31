
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import os

# 股票代碼
stock_id = "3017"
url = f"https://www.cmoney.tw/finance/{stock_id}/f00036"

# 建立 output 目錄（若不存在）
output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "output")
os.makedirs(output_dir, exist_ok=True)

# 啟動 headless 瀏覽器，並禁用通知
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")  # 使用新版 headless 模式
options.add_argument("--disable-gpu")
options.add_experimental_option("prefs", {
    "profile.default_content_setting_values.notifications": 2
})
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(url)

# 捲動到底部觸發 lazy load
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(2)  # 等待資料載入

# 等待 table 載入
wait = WebDriverWait(driver, 10)
table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.tb.tb1")))

# 擷取表格資料
rows = table.find_elements(By.TAG_NAME, "tr")
data = []
for row in rows:
    cols = [td.text.strip() for td in row.find_elements(By.TAG_NAME, "td")]
    if cols and len(cols) >= 11:
        data.append(cols)

driver.quit()

# 欄位名稱
columns = ["日期", "外資買賣超", "投信買賣超", "自營商買賣超", "三大法人合計",
           "外資持股張數", "外資持股比率", "投信持股張數", "投信持股比率",
           "自營商持股張數", "自營商持股比率"]

# 輸出 CSV
df = pd.DataFrame(data, columns=columns)
csv_path = os.path.join(output_dir, f"法人持股_{stock_id}_headless.csv")
df.to_csv(csv_path, index=False, encoding="utf-8-sig")
print(df)
