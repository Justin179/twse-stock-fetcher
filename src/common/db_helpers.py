import pandas as pd
import sqlite3

def fetch_stock_history_from_db(conn: sqlite3.Connection, stock_code: str) -> pd.DataFrame:
    """
    從資料庫中抓取指定股票代碼的歷史收盤價與成交量資料。
    """
    query = '''
        SELECT date, close AS Close, volume AS Volume
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date
    '''
    df = pd.read_sql_query(query, conn, params=(stock_code,))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def fetch_close_history_from_db(stock_id: str, db_path: str = "data/institution.db") -> pd.DataFrame:
    """
    從 SQLite 資料庫中讀取某檔股票的每日收盤價。
    """
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT date, close FROM twse_prices WHERE stock_id = ? ORDER BY date",
            conn, params=(stock_id,)
        )
    finally:
        conn.close()
    return df
