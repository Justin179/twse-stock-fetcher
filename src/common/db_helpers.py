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
