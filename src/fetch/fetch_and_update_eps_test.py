# fetch_and_update_eps_test.py
import sqlite3
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import io
import sys
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import certifi

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

"""
抓取指定股票每季 EPS 並寫入 profitability_ratios
測試版本：僅抓單一股票（例如 2330）
流程：
1. 確認 eps 欄位存在
2. 抓取 MOPS 財報 EPS 資料
3. 寫入資料庫
"""

DB_PATH = "data/institution.db"
TEST_STOCK_ID = "2330"  # 測試用股票代碼

# --------------------------------------------------------
# 1. 確認欄位存在
# --------------------------------------------------------
def ensure_eps_column_exists():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(profitability_ratios)")
    columns = [col[1] for col in cursor.fetchall()]
    if "eps" not in columns:
        cursor.execute("ALTER TABLE profitability_ratios ADD COLUMN eps REAL")
        print("✅ 已新增 eps 欄位")
    else:
        print("ℹ️ 欄位 eps 已存在")
    conn.commit()
    conn.close()

# --------------------------------------------------------
# 2. 從 MOPS 財報抓 EPS
# --------------------------------------------------------


import httpx
from bs4 import BeautifulSoup
import pandas as pd

def fetch_eps_from_mops(stock_id, year):
    url = "https://mops.twse.com.tw/mops/web/ajax_t163sb04"
    payload = {
        'encodeURIComponent': '1',
        'step': '1',
        'firstin': '1',
        'off': '1',
        'keyword4': '',
        'code1': '',
        'TYPEK2': '',
        'checkbtn': '',
        'queryName': 'co_id',
        'TYPEK': '',
        'isnew': 'false',
        'co_id': stock_id,
        'year': str(year - 1911),
        'season': '4'
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/114.0.0.0 Safari/537.36",
        "Referer": "https://mops.twse.com.tw/mops/web/t163sb04",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    try:
        with httpx.Client(verify=False, timeout=10.0) as client:
            res = client.post(url, data=payload, headers=headers)
            res.encoding = 'utf-8'
            print("=== MOPS 回傳內容預覽 ===")
            print(res.text[:1000])  # 只先印前 1000 字避免太多
            print("========================")
            soup = BeautifulSoup(res.text, 'html.parser')
            tables = soup.find_all('table')
            

        all_data = []
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if len(cols) >= 5 and ("基本每股盈餘" in cols[0] or "基本每股" in cols[0]):
                    for q in range(1, 5):
                        try:
                            eps_value = float(cols[q])
                            season_label = f"{year}Q{q}"
                            all_data.append((season_label, eps_value))
                        except:
                            pass

        return pd.DataFrame(all_data, columns=["season", "eps"])
    except Exception as e:
        print(f"❌ {stock_id} {year} 抓取失敗: {e}")
        return pd.DataFrame(columns=["season", "eps"])





# --------------------------------------------------------
# 3. 更新資料庫
# --------------------------------------------------------
def update_eps_to_db(stock_id, season, eps_value):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM profitability_ratios
        WHERE stock_id = ? AND season = ?
    """, (stock_id, season))
    exists = cursor.fetchone()
    if exists:
        cursor.execute("""
            UPDATE profitability_ratios
            SET eps = ?
            WHERE stock_id = ? AND season = ?
        """, (eps_value, stock_id, season))
    else:
        cursor.execute("""
            INSERT INTO profitability_ratios (stock_id, season, eps)
            VALUES (?, ?, ?)
        """, (stock_id, season, eps_value))
    conn.commit()
    conn.close()

# --------------------------------------------------------
# 主程式
# --------------------------------------------------------
def main():

    ensure_eps_column_exists()

    current_year = datetime.now().year
    years_to_fetch = [current_year - 1, current_year]  # 抓去年與今年

    for year in years_to_fetch:
        df_eps = fetch_eps_from_mops(TEST_STOCK_ID, year)
        if df_eps.empty:
            print(f"⚠️ {TEST_STOCK_ID} {year} 無 EPS 資料")
            continue
        for _, row in df_eps.iterrows():
            update_eps_to_db(TEST_STOCK_ID, row["season"], row["eps"])
            print(f"  ➕ {TEST_STOCK_ID} {row['season']} EPS={row['eps']}")

if __name__ == "__main__":
    main()
