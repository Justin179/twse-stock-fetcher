# 檔名: tools/import_stock_list_to_db_fixed.py

import sqlite3
import csv
import os

# 設定資料來源與資料庫路徑
csv_files = [
    os.path.join("data", "twse_StockList.csv"),
    os.path.join("data", "tpex_StockList.csv")
]
db_path = os.path.join("data", "institution.db")

# 連線至 SQLite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 建立表格 (重新建立)
cursor.execute("DROP TABLE IF EXISTS stock_meta")
cursor.execute("""
    CREATE TABLE stock_meta (
        stock_id INTEGER PRIMARY KEY,
        name TEXT,
        market TEXT
    )
""")

inserted_count = 0

def clean_stock_id(raw_id: str) -> str:
    # 去除 ="0050" 或 "0050" 外框
    cleaned = raw_id.strip().lstrip('="').rstrip('"')
    return cleaned

# 處理每個 CSV 檔
for csv_file in csv_files:
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)  # 跳過欄位名稱
        for row in reader:
            stock_id_str = clean_stock_id(row[0])
            if stock_id_str.startswith("0"):
                continue  # 排除 ETF
            try:
                stock_id = int(stock_id_str)
            except ValueError:
                continue
            name = row[1].strip()
            market = row[2].strip()
            cursor.execute("""
                INSERT OR REPLACE INTO stock_meta (stock_id, name, market)
                VALUES (?, ?, ?)
            """, (stock_id, name, market))
            inserted_count += 1

# 完成
conn.commit()
conn.close()
print(f"完成，已寫入 {inserted_count} 筆個股資料到 stock_meta 資料表。")
