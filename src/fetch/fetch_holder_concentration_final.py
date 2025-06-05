from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time

def fetch_holder_concentration_selenium(stock_id="3017"):
    url = f"https://norway.twsthr.info/StockHolders.aspx?stock={stock_id}"

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "Details"))
        )
        time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        table = soup.find("table", id="Details")
        rows = table.find_all("tr")
        print(f"✅ 共找到 {len(rows)} 列 tr")

        data = []
        for i, row in enumerate(rows):
            cols = row.find_all("td")
            if len(cols) >= 14:
                date = cols[2].text.strip().replace("/", "")
                avg_shares = cols[5].text.strip().replace(",", "")
                ratio_1000 = cols[13].text.strip()

                if date.isdigit() and len(date) == 8:
                    data.append({
                        "資料日期": date,
                        "平均張數": avg_shares,
                        ">1000張佔比": ratio_1000
                    })

        driver.quit()
        df = pd.DataFrame(data)
        if df.empty:
            print("❌ 沒有抓到有效資料列")
            return df

        df["資料日期"] = pd.to_datetime(df["資料日期"], format="%Y%m%d", errors="coerce")
        df["平均張數"] = pd.to_numeric(df["平均張數"], errors="coerce")
        df[">1000張佔比"] = pd.to_numeric(df[">1000張佔比"], errors="coerce")

        df.to_csv("holder_concentration_3017.csv", index=False, encoding="utf-8-sig")
        print("✅ 已儲存 CSV：holder_concentration_3017.csv")
        print(df.head())
        return df

    except Exception as e:
        driver.quit()
        print("❌ 發生錯誤：", e)
        return pd.DataFrame()

if __name__ == "__main__":
    fetch_holder_concentration_selenium("3017")