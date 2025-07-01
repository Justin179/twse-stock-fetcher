import sqlite3
import pandas as pd

DB_PATH = "data/institution.db"
OUTPUT_FILE = "temp_list.txt"

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

    # 取得股票代碼
    stock_ids = filtered_df["stock_id"].dropna().astype(str).tolist()

    # 寫入 temp_list.txt（先清空）
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for sid in stock_ids:
            f.write(sid + "\n")

    print(f"✅ 符合條件的股票共 {len(stock_ids)} 檔，已寫入 {OUTPUT_FILE}")

if __name__ == "__main__":
    filter_strong_stocks()
