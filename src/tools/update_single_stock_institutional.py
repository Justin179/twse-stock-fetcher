"""
背景執行：更新單一股票的外資、投信買賣超 & 持股比率資料
使用方式: python src/tools/update_single_stock_institutional.py <stock_id>
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import sqlite3
import time


def update_institutional_data(stock_id):
    """更新單一股票的法人買賣超與持股比率資料（近5日）"""
    
    # DB 初始化
    db_path = os.path.join("data", "institution.db")
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    MAX_RETRIES = 3
    print(f"🔍 處理 {stock_id} ...")
    url = f"https://www.cmoney.tw/finance/{stock_id}/f00036"
    success = False
    update_count = 0

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
            invalid_row_found = False

            for row in rows:
                cols = [td.text.strip().replace(",", "").replace("%", "") for td in row.find_elements(By.TAG_NAME, "td")]
                if cols and len(cols) >= 11 and cols[0] != "日期":
                    try:
                        if any(not cols[i] for i in [1,2,5,6,7,8]):
                            print(f"⚠️ 資料遺漏於 {cols[0]}，跳過 {stock_id}")
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
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
        except Exception as e:
            print(f"❌ 未預期的錯誤: {e}")
            try:
                driver.quit()
            except:
                pass
            break
    
    conn.close()
    
    if success:
        print(f"\n✅ {stock_id} 更新完成！共新增或更新 {update_count} 筆資料")
        return True
    else:
        print(f"\n❌ {stock_id} 更新失敗")
        return False


def main():
    if len(sys.argv) < 2:
        print("❌ 請提供股票代碼")
        sys.exit(1)
    
    stock_id = sys.argv[1]
    print(f"開始更新 {stock_id} 外資、投信買賣超與持股比率資料...")
    
    success = update_institutional_data(stock_id)
    
    # 播放提示音
    if success:
        try:
            import subprocess
            subprocess.run([
                'powershell', '-Command',
                "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\Windows Logon.wav').PlaySync()"
            ], check=False)
        except:
            pass


if __name__ == "__main__":
    main()
