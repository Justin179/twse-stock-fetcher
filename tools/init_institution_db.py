import sqlite3
from pathlib import Path

# 建立資料夾與資料庫檔案
Path("data").mkdir(exist_ok=True)
db_path = "data/institution.db"

# 建立連線並創建資料表
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS institution_daily (
    stock_id TEXT NOT NULL,
    date TEXT NOT NULL,
    foreign_net_buy INTEGER,
    PRIMARY KEY (stock_id, date)
)
""")

conn.commit()
conn.close()
print(f"✅ 已建立 SQLite 資料庫與表格：{db_path}")
