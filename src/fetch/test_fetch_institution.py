import httpx
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
from pathlib import Path

# === 設定資料庫 ===
db_path = Path("data/institution.db")
db_path.parent.mkdir(exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 確保資料表存在
cursor.execute("""
CREATE TABLE IF NOT EXISTS institution_daily (
    stock_id TEXT NOT NULL,
    date TEXT NOT NULL,
    foreign_net_buy INTEGER,
    PRIMARY KEY (stock_id, date)
)
""")
conn.commit()

# === 設定查詢區間 ===
today = datetime.today()
dates = [today - timedelta(days=i) for i in range(15)]  # 多取幾天避開假日
dates = sorted(set(d.strftime("%Y-%m-%d") for d in dates))

# 查詢 DB 已有的日期資料
existing = pd.read_sql_query("SELECT DISTINCT date FROM institution_daily", conn)
db_dates = set(existing["date"])

# 過濾出還沒抓的日期
target_dates = [d for d in dates if d not in db_dates]
print(f"📆 尚需抓取日期：{target_dates}")

# === 抓取缺漏資料 ===
for date_str in target_dates:
    url = f"https://www.twse.com.tw/fund/TWT38U?response=json&date={date_str.replace('-', '')}"
    try:
        print(f"🔍 請求中：{url}")
        resp = httpx.get(url, timeout=10.0, verify=False)
        data = resp.json()
        if not data.get("data"):
            continue

        insert_rows = []
        for row in data["data"]:
            stock_id = row[1].strip()
            try:
                foreign = int(row[5].replace(",", "").replace("--", "0"))
            except:
                continue
            insert_rows.append((stock_id, date_str, foreign))

        cursor.executemany(
            "INSERT OR IGNORE INTO institution_daily (stock_id, date, foreign_net_buy) VALUES (?, ?, ?)",
            insert_rows
        )
        conn.commit()
        print(f"✅ 已寫入 {len(insert_rows)} 筆：{date_str}")
        time.sleep(0.3)
    except Exception as e:
        print(f"❌ {date_str} 請求失敗: {e}")
        continue

conn.close()
print("🎉 完成資料更新")
