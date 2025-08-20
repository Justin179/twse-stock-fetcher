# fetch_wantgoo_main_trend.py
# WantGoo 主力進出動向：抓 日期、收盤價、買賣超、家數差 -> SQLite: data/institution.db (table: main_force_trading)
# 參數：
#   python fetch_wantgoo_main_trend.py              # 讀 my_stock_holdings.txt
#   python fetch_wantgoo_main_trend.py 2330         # 單檔
#   python fetch_wantgoo_main_trend.py list.txt     # 清單檔

import os
import re
import sys
import time
import sqlite3
from typing import List, Tuple

from selenium import webdriver
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

DB_PATH = "data/institution.db"
MAX_RETRY = 3
PAGE_LOAD_TIMEOUT = 30
WAIT_TIMEOUT = 25

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

_num_re = re.compile(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?")

def _clean_number(s: str, is_int=False):
    s = (s or "").strip().replace("—", "-").replace("−", "-")
    m = _num_re.search(s)
    if not m:
        raise ValueError("no number")
    v = m.group(0).replace(",", "")
    return int(float(v)) if is_int else float(v)

def _build_driver(headless: bool = True) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1400,2500")
    options.add_argument(f"user-agent={UA}")
    options.add_argument("--lang=zh-TW,zh")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # 降低廣告干擾
    options.add_argument("--blink-settings=imagesEnabled=true")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    # 反自動化痕跡
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW','zh']});
            Object.defineProperty(Intl.DateTimeFormat().resolvedOptions(), 'timeZone', {get: () => 'Asia/Taipei'});
        """
    })
    return driver

def _robust_scroll_and_wait(driver: webdriver.Chrome) -> bool:
    wait = WebDriverWait(driver, WAIT_TIMEOUT)
    table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table#main-trend")))
    # 先到表格附近
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", table)
    time.sleep(0.6)

    actions = ActionChains(driver)

    # 多輪上下滾動 + 觸發 wheel/scroll/mousemove
    for _ in range(4):
        driver.execute_script("window.scrollBy(0, 700);")
        actions.key_down(Keys.PAGE_DOWN).key_up(Keys.PAGE_DOWN).perform()
        driver.execute_script("""
            window.dispatchEvent(new Event('scroll'));
            window.dispatchEvent(new WheelEvent('wheel', {deltaY: 400}));
            document.body.dispatchEvent(new Event('mousemove'));
        """)
        time.sleep(0.35)

    for _ in range(2):
        driver.execute_script("window.scrollBy(0, -600);")
        actions.key_down(Keys.PAGE_UP).key_up(Keys.PAGE_UP).perform()
        driver.execute_script("""
            window.dispatchEvent(new Event('scroll'));
            window.dispatchEvent(new WheelEvent('wheel', {deltaY: -300}));
        """)
        time.sleep(0.3)

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", table)
    time.sleep(0.5)

    # 等 rows 真的進來（>0 且第一列至少 4 欄）
    t0 = time.time()
    while time.time() - t0 < WAIT_TIMEOUT:
        rows = driver.find_elements(By.CSS_SELECTOR, "#main-trend tbody tr")
        if rows:
            tds = rows[0].find_elements(By.TAG_NAME, "td")
            if len(tds) >= 4 and tds[0].text.strip():
                return True
        time.sleep(0.4)

    return False

def fetch_wantgoo_main_trend(stock_id: str) -> List[Tuple[str, str, float, int, int]]:
    url = f"https://www.wantgoo.com/stock/{stock_id}/major-investors/main-trend"

    # 先 headless 試，失敗後自動改非 headless 再試一次，利於被防爬時載入
    headless_try_order = [True, False]

    for attempt in range(1, MAX_RETRY + 1):
        for headless in headless_try_order:
            driver = None
            try:
                driver = _build_driver(headless=headless)
                driver.get(url)

                # 等頁面主架構
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "main.main"))
                )
                time.sleep(0.8)

                # 滾到表格並等待 rows
                if not _robust_scroll_and_wait(driver):
                    raise TimeoutException("表格 rows 載入逾時")

                rows = driver.find_elements(By.CSS_SELECTOR, "#main-trend tbody tr")
                data = []
                for r in rows:
                    tds = r.find_elements(By.TAG_NAME, "td")
                    if len(tds) < 4:
                        continue
                    date_txt = tds[0].text.strip()
                    close_txt = tds[1].text.strip()
                    net_txt = tds[2].text.strip()
                    diff_txt = tds[3].text.strip()
                    try:
                        close_price = _clean_number(close_txt, is_int=False)
                        net_buy_sell = _clean_number(net_txt, is_int=True)
                        dealer_diff = _clean_number(diff_txt, is_int=True)
                    except ValueError:
                        continue
                    data.append((stock_id, date_txt, float(close_price), int(net_buy_sell), int(dealer_diff)))

                driver.quit()
                return data

            except (TimeoutException, WebDriverException) as e:
                print(f"[WARN] {stock_id} 第 {attempt}/{MAX_RETRY} 次抓取失敗 (headless={headless}): {e}")
                try:
                    if driver:
                        driver.quit()
                except Exception:
                    pass
                # 換另一個 headless 狀態再試；兩個都失敗才算一輪失敗
                continue
            except Exception as e:
                print(f"[ERROR] {stock_id} 發生例外: {e}")
                try:
                    if driver:
                        driver.quit()
                except Exception:
                    pass
                return []

        # 兩種 headless 狀態都失敗，進入下一輪重試
        time.sleep(1.0)

    print(f"[ERROR] {stock_id} 重試失敗，跳過")
    return []

def save_to_db(rows: List[Tuple[str, str, float, int, int]], db_path: str = DB_PATH) -> int:
    if not rows:
        return 0
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS main_force_trading (
            stock_id TEXT,
            date TEXT,
            close_price REAL,
            net_buy_sell INTEGER,
            dealer_diff INTEGER,
            PRIMARY KEY (stock_id, date)
        )
    """)
    success = 0
    for row in rows:
        cur.execute("""
            INSERT OR IGNORE INTO main_force_trading
            (stock_id, date, close_price, net_buy_sell, dealer_diff)
            VALUES (?, ?, ?, ?, ?)
        """, row)
        if cur.rowcount > 0:
            success += 1
    conn.commit()
    conn.close()
    return success

def _read_stock_list(fp: str):
    with open(fp, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        stocks = _read_stock_list("my_stock_holdings.txt")
        print(f"[LIST] 使用股票清單: my_stock_holdings.txt ({len(stocks)} 檔)")
    else:
        arg = args[0]
        if arg.endswith(".txt") and os.path.exists(arg):
            stocks = _read_stock_list(arg)
            print(f"[LIST] 使用股票清單: {arg} ({len(stocks)} 檔)")
        else:
            stocks = [arg]
            print(f"[SINGLE] 單檔執行: {arg}")

    for sid in stocks:
        print(f"[FETCH] 抓取 {sid} WantGoo 主力進出動向...")
        recs = fetch_wantgoo_main_trend(sid)
        if not recs:
            print(f"[SKIP] {sid} 無可寫入資料")
            continue
        n = save_to_db(recs)
        print(f"[OK] {sid} 新增 {n} 筆 (不含重複)")
    print("[DONE] 完成")
