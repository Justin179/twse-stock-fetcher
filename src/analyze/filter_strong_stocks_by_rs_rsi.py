# src/analyze/filter_strong_stocks_by_rs_rsi.py
import sqlite3
import pandas as pd

DB_PATH = "data/institution.db"
OUTPUT_FILE = "high_relative_strength_stocks.txt"

def filter_strong_stocks():
    # 連接資料庫
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT stock_id, rs_score_1y, rs_score_ytd, rsi14 FROM stock_rs_rsi",
        conn
    )
    conn.close()

    # RS > 90 (1Y 或 YTD)
    rs_mask = (df["rs_score_1y"] > 90) | (df["rs_score_ytd"] > 90)

    # RSI >= 30（排除 RSI < 30 的弱勢股）
    rsi_mask = df["rsi14"] >= 30

    # 綜合篩選條件 → 取得股票代碼
    filtered_df = df[rs_mask & rsi_mask]
    stock_ids = filtered_df["stock_id"].dropna().astype(str).tolist()

    # 以前版本：會在檔案中尋找「# 找出RS>90的強勢股」標記行後覆寫
    # 現在 high_relative_strength_stocks.txt 已不保留任何 # 註解
    # → 直接清空檔案並重寫乾淨清單（去重＋排序）
    unique_sorted = sorted(set(stock_ids))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for sid in unique_sorted:
            f.write(f"{sid}\n")

    print(f"✅ 符合條件的股票共 {len(unique_sorted)} 檔，已覆寫 {OUTPUT_FILE}")

if __name__ == "__main__":
    filter_strong_stocks()
