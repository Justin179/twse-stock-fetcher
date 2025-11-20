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
    df["High10_prev"] = df["Close"].shift(1).rolling(window=10).max()


    # KD / RSI 指標已移除（保留空區塊供未來擴充）

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
        c4 = row["Close"] > row["High10_prev"]
        c5 = row["MA5"] > row["MA10"] > row["MA24"]
        c6 = row["Close"] > row["Close_5days_ago"] and row["Close"] > row["Close_10days_ago"] and row["Close"] > row["Close_24days_ago"]
        c7 = row["Close_4days_ago"] > row["Close_5days_ago"] and row["Close"] > row["Close_Yesterday"] and row["Volume"] > row["Volume_Yesterday"]
        results.append({
            "日期": date,
            "價量同步": check(c1),
            "扣抵變高但價漲量增(強勢股)": check(c7),
            "站上5日均線(> MA5)": check(c2),
            "站上基準價(上彎5日均線)": check(c3),
            "站上扣抵值(>)": check(c10),
            "創10日收盤新高(>)": check(c4),
            "短中均線(5 10 24)多頭排列": check(c5),
            "短中均線(5 10 24)皆上彎": check(c6)
        })

    # 建立表格
    rotated = pd.DataFrame(results).set_index("日期").T
    rotated["條件名稱"] = rotated.index

    # 補全空白讓 row 高度一致(無效)
    max_len = max(rotated["條件名稱"].apply(len))
    rotated["條件名稱"] = rotated["條件名稱"].apply(lambda x: x.ljust(max_len, '　'))  # 全形空格補齊


    rotated = rotated.reset_index(drop=True)
    columns = [col for col in rotated.columns if col != "條件名稱"]

    # --- 新增：以關鍵字群組並給予不同底色以視覺區隔 ---
    # 定義群組關鍵字與顏色（可依需求增刪或調整顏色）
    group_rules = [
        ("站上", "rgba(255,200,200,0.45)"),       # 淺紅：所有包含「站上」的條件
        ("短中均線", "rgba(200,220,255,0.45)"),  # 淺藍：所有包含「短中均線」的條件
    ]

    # 針對每一 row 的條件名稱決定底色
    row_labels = rotated["條件名稱"].astype(str).tolist()
    row_colors = []
    for lbl in row_labels:
        matched = False
        for key, color in group_rules:
            if key in lbl:
                row_colors.append(color)
                matched = True
                break
        if not matched:
            # 使用與原本相近的淡背景
            row_colors.append("white")

    # Plotly 要求每一個欄位都提供一組 row color list，所以重複 row_colors
    num_columns = len(rotated.columns)  # 包含條件名稱欄
    cell_fill = [row_colors for _ in range(num_columns)]

    fig = go.Figure(data=[
        go.Table(
            columnwidth=[3] + [1] * len(columns),
            header=dict(
                values=["條件名稱"] + columns,
                fill_color='paleturquoise',
                align='left',
                font=dict(size=14)
            ),
            cells=dict(
                values=[rotated["條件名稱"]] + [rotated[col] for col in columns],
                fill_color=cell_fill,
                align='left',
                font=dict(size=14),
                line=dict(color='lightgrey', width=1)  # 加細邊線以強化分隔
            )
        )
    ])

    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        height=60 + 28 * len(rotated)  # 動態高度
    )

    return fig


if __name__ == "__main__":
    pio.renderers.default = "browser"
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock_id", type=str, default="2330", help="股票代號")
    args = parser.parse_args()

    fig = analyze_10day_strength(args.stock_id)
    fig.show()
