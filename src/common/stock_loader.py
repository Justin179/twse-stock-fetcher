import sqlite3
import pandas as pd

# 讀取持股清單與公司名稱
def load_stock_list_with_names(file_path="my_stock_holdings.txt", db_path="data/institution.db"):
    """讀取持股股票清單與名稱對照，回傳 stock_id 清單與顯示選項清單"""
    with open(file_path, "r", encoding="utf-8") as f:
        stocks = sorted(
            line.strip() for line in f
            if line.strip() and not line.strip().startswith("#")
        )

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT stock_id, name FROM stock_meta", conn)
    conn.close()

    id_name_map = dict(zip(df["stock_id"].astype(str), df["name"]))
    display_options = [
        f"{stock_id} {id_name_map[stock_id]}" if stock_id in id_name_map else stock_id
        for stock_id in stocks
    ]
    return stocks, display_options
