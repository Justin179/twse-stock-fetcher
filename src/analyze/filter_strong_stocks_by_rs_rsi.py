import sqlite3
import pandas as pd

DB_PATH = "data/institution.db"
OUTPUT_FILE = "high_relative_strength_stocks.txt"

def filter_strong_stocks():
    # 連接資料庫
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT stock_id, rs_score_1y, rs_score_ytd, rsi14 FROM stock_rs_rsi", conn)
    conn.close()

    # RS > 90 (1Y 或 YTD)
    rs_mask = (df["rs_score_1y"] > 90) | (df["rs_score_ytd"] > 90)

    # RSI >= 30（排除 RSI < 30 的弱勢股）
    rsi_mask = df["rsi14"] >= 30

    # 綜合篩選條件
    filtered_df = df[rs_mask & rsi_mask]
    stock_ids = filtered_df["stock_id"].dropna().astype(str).tolist()

    # 讀取原本的 high_relative_strength_stocks.txt
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 找出 "# 找出RS>90的強勢股" 這一行的 index
    try:
        insert_idx = next(i for i, line in enumerate(lines) if "# 找出RS>90的強勢股" in line) + 1
    except StopIteration:
        print("❌ 找不到 '# 找出RS>90的強勢股' 標記")
        return

    # 重組內容：保留前面內容 + 插入新股票清單
    new_lines = lines[:insert_idx] + [sid + "\n" for sid in stock_ids]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"✅ 符合條件的股票共 {len(stock_ids)} 檔，已寫入 {OUTPUT_FILE} 中的強勢股區段")

if __name__ == "__main__":
    filter_strong_stocks()
