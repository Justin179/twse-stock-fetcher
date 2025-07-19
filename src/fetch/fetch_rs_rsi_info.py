# src/data/fetch_rs_rsi_info.py

import sqlite3
import pandas as pd

# 讀取個股 RS / RSI 評分資訊
def fetch_rs_rsi_info(stock_id: str, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    query = """
        SELECT return_1y, rs_score_1y, return_ytd, rs_score_ytd, rsi14, updated_at
        FROM stock_rs_rsi
        WHERE stock_id = ?
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()
    return df.iloc[0] if not df.empty else None
