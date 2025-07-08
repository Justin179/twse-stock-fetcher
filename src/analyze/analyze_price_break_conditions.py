import sqlite3
import pandas as pd
from datetime import datetime
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from common.login_helper import get_logged_in_sdk
from src.fetch.fetch_latest_price_full import fetch_and_store_price

DB_PATH = "data/institution.db"

def get_recent_prices(stock_id, today_date):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT date, close, high, low, volume 
        FROM twse_prices 
        WHERE stock_id = ? AND date < ? 
        ORDER BY date DESC LIMIT 2
        """,
        conn, params=(stock_id, today_date)
    )
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_yesterday_hl(stock_id, today_date):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT date, high, low 
        FROM twse_prices 
        WHERE stock_id = ? AND date < ? 
        ORDER BY date DESC LIMIT 1
        """,
        conn, params=(stock_id, today_date)
    )
    conn.close()
    if len(df) < 1:
        return None, None
    return df.iloc[0]["high"], df.iloc[0]["low"]


def get_week_month_high_low(stock_id):
    today = datetime.today()
    current_year, current_week, _ = today.isocalendar()

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, high, low FROM twse_prices WHERE stock_id = ?", conn, params=(stock_id,)
    )
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.isocalendar().year
    df["week"] = df["date"].dt.isocalendar().week
    df["month"] = df["date"].dt.month

    # 上週
    prev_week = current_week - 1
    year = current_year
    for _ in range(10):
        week_df = df[(df["year"] == year) & (df["week"] == prev_week)]
        if not week_df.empty:
            w1 = week_df["high"].max()
            w2 = week_df["low"].min()
            break
        prev_week -= 1
        if prev_week <= 0:
            year -= 1
            prev_week = 52
    else:
        w1 = w2 = None

    # 上月
    prev_month = today.month - 1 or 12
    prev_month_year = today.year - 1 if today.month == 1 else today.year
    month_df = df[(df["date"].dt.year == prev_month_year) & (df["date"].dt.month == prev_month)]

    if not month_df.empty:
        m1 = month_df["high"].max()
        m2 = month_df["low"].min()
    else:
        m1 = m2 = None

    return w1, w2, m1, m2

def get_today_prices(stock_id):
    sdk = get_logged_in_sdk()
    sdk.init_realtime()
    quote = sdk.marketdata.rest_client.stock.intraday.quote(symbol=stock_id)
    sdk.logout()
    return {
        "date": quote.get("date"),
        "c1": quote.get("closePrice"),
        "o": quote.get("openPrice"),
        "c2": quote.get("previousClose")
    }

def analyze_stock(stock_id):
    fetch_and_store_price(stock_id)  # 確保資料最新
    today = get_today_prices(stock_id)
    today_date = today["date"]  # 這是今天的日期字串

    db_data = get_recent_prices(stock_id, today_date)
    w1, w2, m1, m2 = get_week_month_high_low(stock_id)
    h, l = get_yesterday_hl(stock_id, today_date)

    c1, o, c2 = today["c1"], today["o"], today["c2"]
    v1 = db_data.iloc[0]["volume"] if len(db_data) > 0 else None
    v2 = db_data.iloc[1]["volume"] if len(db_data) > 1 else None

    print("🔍 變數內容檢查：")
    print(f"  ▸ 今日收盤價 (c1)：{c1}")
    print(f"  ▸ 今日開盤價 (o)：{o}")
    print(f"  ▸ 昨日收盤價 (c2)：{c2}")
    print(f"  ▸ 昨日高點 (h)：{h}")
    print(f"  ▸ 昨日低點 (l)：{l}")
    print(f"  ▸ 昨成交量 (v1)：{v1}")
    print(f"  ▸ 前天成交量 (v2)：{v2}")
    print(f"  ▸ 上週高點 (w1)：{w1}")
    print(f"  ▸ 上週低點 (w2)：{w2}")
    print(f"  ▸ 上月高點 (m1)：{m1}")
    print(f"  ▸ 上月低點 (m2)：{m2}")
    print("-" * 40)


    signals = []

    # 昨天收盤
    if c2:
        if w1 and c2 > w1:
            signals.append("昨收盤過上週高點")
            if v1 and v2 and v1 > v2:
                signals.append("昨收盤帶量過上週高點")
        if m1 and c2 > m1:
            signals.append("昨收盤過上月高點")
            if v1 and v2 and v1 > v2:
                signals.append("昨收盤帶量過上月高點")
        if w2 and c2 < w2:
            signals.append("昨收盤破上週低點")
            if v1 and v2 and v1 > v2:
                signals.append("昨收盤帶量破上週低點")
        if m2 and c2 < m2:
            signals.append("昨收盤破上月低點")
            if v1 and v2 and v1 > v2:
                signals.append("昨收盤帶量破上月低點")

    # 今天開盤
    if o and c2:
        if o > c2:
            signals.append("今開盤開高")
        elif o == c2:
            signals.append("今開盤開平盤")
        elif o < c2:
            signals.append("今開盤開低")
        if h and o > h:
            signals.append("今開盤過昨高")
        if l and o < l:
            signals.append("今開盤破昨低")
        if w1 and o > w1:
            signals.append("今開盤過上週高點")
        if m1 and o > m1:
            signals.append("今開盤過上月高點")
        if w2 and o < w2:
            signals.append("今開盤破上週低點")
        if m2 and o < m2:
            signals.append("今開盤破上月低點")

    # 今天盤中
    if c1:
        if h and c1 > h:
            signals.append("今收盤過昨高")
        if l and c1 < l:
            signals.append("今收盤破昨低")
        if w1 and c1 > w1:
            signals.append("今收盤過上週高點")
        if w2 and c1 < w2:
            signals.append("今收盤破上週低點")
        if m1 and c1 > m1:
            signals.append("今收盤過上月高點")
        if m2 and c1 < m2:
            signals.append("今收盤破上月低點")

    return signals

if __name__ == "__main__":
    stock_id = "3017"
    results = analyze_stock(stock_id)
    print(f"📢 [{stock_id}] 提示訊號：")
    for r in results:
        print("✅", r)
