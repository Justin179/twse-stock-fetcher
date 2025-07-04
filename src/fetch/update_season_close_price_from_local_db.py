
import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

'''
補上 profitability_ratios 資料表中缺少的季收盤價
1 確認欄位存在
2 讀取股票清單
3 篩出該股票哪些季的收盤價還沒補
4 從 twse_prices 資料表中抓取最近的收盤價
5 更新 profitability_ratios 資料表
'''

DB_PATH = "data/institution.db"

def ensure_column_exists():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(profitability_ratios)")
    columns = [col[1] for col in cursor.fetchall()]
    if "season_close_price" not in columns:
        cursor.execute("ALTER TABLE profitability_ratios ADD COLUMN season_close_price REAL")
        print("✅ 已新增 season_close_price 欄位")
    else:
        print("ℹ️ 欄位 season_close_price 已存在")
    conn.commit()
    conn.close()

def load_stock_list():
    stock_file = "my_stock_holdings.txt"
    for arg in sys.argv:
        if arg.endswith(".txt") and os.path.exists(arg):
            stock_file = arg
            break
    print(f"📄 使用的股票清單: {stock_file}")
    with open(stock_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def get_season_end_date(season: str) -> str:
    season_to_month = {
        "Q1": "0331",
        "Q2": "0630",
        "Q3": "0930",
        "Q4": "1231",
    }
    return f"{season[:4]}{season_to_month[season[-2:]]}"

def get_missing_season_closes(stock_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT season FROM profitability_ratios
        WHERE stock_id = ? AND (season_close_price IS NULL OR season_close_price = '')
    """, (stock_id,))
    rows = [row[0] for row in cursor.fetchall()]
    conn.close()
    return rows

def fetch_season_close_from_prices(stock_id, season_end_date):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"""
        SELECT date, close FROM twse_prices
        WHERE stock_id = '{stock_id}'
    """, conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    target_date = pd.to_datetime(season_end_date, format="%Y%m%d", errors="coerce")

    # 找出最接近目標日且 <= 目標日的最後一筆交易日
    df_valid = df[df["date"] <= target_date]
    if df_valid.empty:
        return None

    # iloc[-1] 是最後一列 = 最接近季末日的那個交易日
    nearest_row = df_valid.iloc[-1]
    return round(nearest_row["close"], 2)


def update_season_close_price(stock_id, season, close_price):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE profitability_ratios
        SET season_close_price = ?
        WHERE stock_id = ? AND season = ?
    """, (close_price, stock_id, season))
    conn.commit()
    conn.close()

def main():
    ensure_column_exists()
    stock_list = load_stock_list()

    for stock_id in stock_list:
        missing_seasons = get_missing_season_closes(stock_id)
        if not missing_seasons:
            print(f"✅ {stock_id} 無需補季收盤價")
            continue

        print(f"📌 {stock_id} 需補 {len(missing_seasons)} 筆季收盤價")
        for season in missing_seasons:
            season_end = get_season_end_date(season)
            close_price = fetch_season_close_from_prices(stock_id, season_end)
            if close_price is not None:
                update_season_close_price(stock_id, season, close_price)
                print(f"  ➕ {stock_id} {season} 補上收盤價 {close_price}")
            else:
                print(f"  ⚠️ {stock_id} {season} 查無 {season_end} 收盤價")

if __name__ == "__main__":
    main()
