# plot_price_interactive.py

import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
pio.renderers.default = "browser"  # 👉 指定用預設瀏覽器開啟

def plot_price_interactive(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    query = """
        SELECT date, close
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT 60
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()

    if df.empty:
        print(f"找不到股票 {stock_id} 的資料")
        return

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["label"] = df["date"].dt.strftime("%m/%d")  # 月/日，不補零（Linux/Mac 可用，Windows 需改為 %#m/%#d）

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["label"],
        y=df["close"],
        mode="lines+markers",
        name="收盤價",
        line=dict(color="orange", width=2),
        marker=dict(size=6),
        hovertemplate="收盤價：%{y}<extra></extra>"
    ))

    fig.update_layout(
        title=f"{stock_id} 過去60個交易日收盤價",
        xaxis=dict(title="日期", type="category", tickangle=-45),
        yaxis=dict(title="收盤價"),
        height=400,
        hovermode="x unified",
        margin=dict(t=40, b=40)
    )

    fig.show()

if __name__ == "__main__":
    plot_price_interactive("2330", "data/institution.db")
