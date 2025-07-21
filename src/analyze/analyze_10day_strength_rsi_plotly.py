import pandas as pd
import sqlite3
from datetime import datetime
import plotly.graph_objects as go
import argparse
import plotly.io as pio

def analyze_10day_strength(stock_id: str) -> go.Figure:
    conn = sqlite3.connect("data/institution.db")
    query = """
    SELECT date AS Date, close AS Close, volume AS Volume
    FROM twse_prices
    WHERE stock_id = ?
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")

    # 技術指標計算
    df["Close_Yesterday"] = df["Close"].shift(1)
    df["Volume_Yesterday"] = df["Volume"].shift(1)
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA10"] = df["Close"].rolling(window=10).mean()
    df["MA24"] = df["Close"].rolling(window=24).mean()
    df["Close_4days_ago"] = df["Close"].shift(4)
    df["Close_5days_ago"] = df["Close"].shift(5)
    df["Close_10days_ago"] = df["Close"].shift(10)
    df["Close_24days_ago"] = df["Close"].shift(24)
    df["High10"] = df["Close"].rolling(window=10).max()

    # KD
    low9 = df["Close"].rolling(window=9).min()
    high9 = df["Close"].rolling(window=9).max()
    rsv = (df["Close"] - low9) / (high9 - low9) * 100
    df["K"] = rsv.ewm(com=2).mean()
    df["D"] = df["K"].ewm(com=2).mean()
    df["K_prev"] = df["K"].shift(1)
    df["D_prev"] = df["D"].shift(1)

    # RSI
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    df["RSI_Yesterday"] = df["RSI"].shift(1)

    # 條件分析
    analysis_days = df.tail(10).copy()
    results = []

    for _, row in analysis_days.iterrows():
        check = lambda b: "✅" if b else "❌"
        date = row["Date"].strftime("%m-%d")

        c1 = (row["Close"] > row["Close_Yesterday"] and row["Volume"] > row["Volume_Yesterday"]) or \
             (row["Close"] < row["Close_Yesterday"] and row["Volume"] < row["Volume_Yesterday"])
        c2 = row["Close"] > row["MA5"]
        c3 = row["Close"] > row["Close_5days_ago"]
        c10 = row["Close"] > row["Close_4days_ago"]
        c4 = row["Close"] > row["High10"]
        c5 = row["MA5"] > row["MA10"] > row["MA24"]
        c6 = row["Close"] > row["Close_5days_ago"] and row["Close"] > row["Close_10days_ago"] and row["Close"] > row["Close_24days_ago"]
        c7 = row["Close_4days_ago"] > row["Close_5days_ago"] and row["Close"] > row["Close_Yesterday"] and row["Volume"] > row["Volume_Yesterday"]
        c8 = row["K"] > row["D"] and row["K_prev"] < row["D_prev"] and row["K"] < 50
        c9 = row["RSI"] > row["RSI_Yesterday"] and row["RSI_Yesterday"] < 45 and row["RSI"] > 30

        results.append({
            "日期": date,
            "價量同步": check(c1),
            "扣抵變高但價漲量增(強勢股)": check(c7),
            "站上 5日均線(> MA5)": check(c2),
            "上彎 5日均線(站上基準價)": check(c3),
            "站上扣抵值(>)": check(c10),
            "創10日新高(>)": check(c4),
            "短中均線(5 10 24)多頭排列": check(c5),
            "短中均線(5 10 24)皆上彎": check(c6),
            "KD 金叉（低檔）": check(c8),
            "RSI 低檔翻揚": check(c9)
        })

    # 建立表格
    rotated = pd.DataFrame(results).set_index("日期").T
    rotated["條件名稱"] = rotated.index

    # 補全空白讓 row 高度一致(無效)
    max_len = max(rotated["條件名稱"].apply(len))
    rotated["條件名稱"] = rotated["條件名稱"].apply(lambda x: x.ljust(max_len, '　'))  # 全形空格補齊


    rotated = rotated.reset_index(drop=True)
    columns = [col for col in rotated.columns if col != "條件名稱"]

    fig = go.Figure(data=[
        go.Table(
            columnwidth=[2] + [1] * len(columns),
            header=dict(
                values=["條件名稱"] + columns,
                fill_color='paleturquoise',
                align='left',
                font=dict(size=14)
            ),
            cells=dict(
                values=[rotated["條件名稱"]] + [rotated[col] for col in columns],
                fill_color='lavender',
                align='left',
                font=dict(size=14)
            )
        )
    ])

    fig.update_layout(title=f"{stock_id} - 過去10日條件分析")
    return fig


if __name__ == "__main__":
    pio.renderers.default = "browser"
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock_id", type=str, default="2330", help="股票代號")
    args = parser.parse_args()

    fig = analyze_10day_strength(args.stock_id)
    fig.show()
