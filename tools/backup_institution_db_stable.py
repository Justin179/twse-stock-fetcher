import sqlite3
from datetime import datetime
from pathlib import Path

# 推導專案根目錄（從 tools/ 回到上層）
root_dir = Path(__file__).resolve().parent.parent
src_db = root_dir / "data/institution.db"
dst_dir = root_dir / "backup"

# 備份檔案名稱加日期
today = datetime.now().strftime("%Y%m%d")
dst_dir.mkdir(exist_ok=True)
dst_db = dst_dir / f"institution_{today}.db"

# 使用 SQLite 的 .backup 方法備份
with sqlite3.connect(src_db) as src_conn:
    with sqlite3.connect(dst_db) as dst_conn:
        src_conn.backup(dst_conn)

print(f"✅ 備份成功：{dst_db}")