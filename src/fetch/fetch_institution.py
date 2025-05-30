import httpx
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
from pathlib import Path

"""
下載 TWSE 外資與投信每日買賣超資料(全上市公司)
存入 institution_daily 資料表 
"""
# === 設定資料庫 ===
db_path = Path("data/institution.db")
db_path.parent.mkdir(exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 確保資料表存在（新增 trust_net_buy 欄位）
cursor.execute("""
CREATE TABLE IF NOT EXISTS institution_daily (
    stock_id TEXT NOT NULL,
    date TEXT NOT NULL,
    foreign_net_buy INTEGER,
    trust_net_buy INTEGER,
    PRIMARY KEY (stock_id, date)
)
""")
conn.commit()

# === 設定查詢區間 ===
today = datetime.today()
dates = [today - timedelta(days=i) for i in range(99)]  # 多取幾天避開假日(實際需要的交易日是60天)
dates = sorted(set(d.strftime("%Y-%m-%d") for d in dates))

# 查詢 DB 已有的日期資料
existing = pd.read_sql_query("SELECT DISTINCT date FROM institution_daily", conn)
db_dates = set(existing["date"])

# 過濾出還沒抓的日期
target_dates = [d for d in dates if d not in db_dates]
print(f"📆 尚需抓取日期：{target_dates}")

# === 抓取缺漏資料 ===
for date_str in target_dates:
    date_api = date_str.replace("-", "")

    # --- 外資資料 ---
    url_foreign = f"https://www.twse.com.tw/fund/TWT38U?response=json&date={date_api}"
    try:
        print(f"🔍 外資請求中：{url_foreign}")
        resp = httpx.get(url_foreign, timeout=10.0, verify=False)
        data = resp.json()
        if not data.get("data"):
            print(f"⚠️ {date_str} 無資料，跳過（可能為非交易日）")
            continue

        foreign_dict = {}
        for row in data["data"]:
            stock_id = row[1].strip()
            try:
                foreign = int(row[5].replace(",", "").replace("--", "0"))
                foreign_dict[stock_id] = foreign
            except:
                continue
    except Exception as e:
        print(f"❌ 外資資料請求失敗 {date_str}: {e}")
        continue

    # --- 投信資料 ---
    url_trust = f"https://www.twse.com.tw/fund/TWT44U?response=json&date={date_api}"
    try:
        print(f"🔍 投信請求中：{url_trust}")
        resp = httpx.get(url_trust, timeout=10.0, verify=False)
        data = resp.json()
        if not data.get("data"):
            print(f"⚠️ {date_str} 無資料，跳過（可能為非交易日）")
            continue

        trust_dict = {}
        for row in data["data"]:
            stock_id = row[1].strip()
            try:
                trust = int(row[5].replace(",", "").replace("--", "0"))
                trust_dict[stock_id] = trust
            except:
                continue
    except Exception as e:
        print(f"❌ 投信資料請求失敗 {date_str}: {e}")
        continue

    # --- 合併寫入 ---
    insert_rows = []
    all_stock_ids = set(foreign_dict) | set(trust_dict)
    for stock_id in all_stock_ids:
        f = foreign_dict.get(stock_id)
        t = trust_dict.get(stock_id)
        insert_rows.append((stock_id, date_str, f, t))

    cursor.executemany(
        "INSERT OR IGNORE INTO institution_daily (stock_id, date, foreign_net_buy, trust_net_buy) VALUES (?, ?, ?, ?)",
        insert_rows
    )
    conn.commit()
    print(f"✅ 已寫入 {len(insert_rows)} 筆：{date_str}")
    time.sleep(0.3)

conn.close()
print("🎉 完成資料更新")
