# plot_price_interactive.py

import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
pio.renderers.default = "browser"

def plot_price_interactive(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)

    # 取得股票名稱（如果有 stock_meta 資料表）
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM stock_meta WHERE stock_id = ?", (stock_id,))
        row = cursor.fetchone()
        stock_name = row[0] if row else stock_id
    except:
        stock_name = stock_id

    # 取得收盤價資料
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
    df["label"] = df["date"].dt.strftime("%#m/%#d")  # Windows

    fig = go.Figure()
    # 左軸 trace
    fig.add_trace(go.Scatter(
        x=df["label"],
        y=df["close"],
        mode="lines+markers",
        name="收盤價",
        line=dict(color="orange", width=2),
        marker=dict(size=6),
        hovertemplate="收盤價：%{y}<extra></extra>",
        yaxis="y"  # 左軸
    ))

    # 右軸 trace（幾乎一樣）
    fig.add_trace(go.Scatter(
        x=df["label"],
        y=df["close"],
        mode="lines+markers",
        line=dict(color="orange", width=2, dash="dot"),
        marker=dict(size=0),
        yaxis="y2",
        showlegend=False,
        hoverinfo="skip"
    ))


    fig.update_layout(
        title=f"{stock_name} ({stock_id}) 過去60個交易日收盤價",
        xaxis=dict(title="日期", type="category", tickangle=-45),
        yaxis=dict(title=dict(text="收盤價", font=dict(color="orange")), tickfont=dict(color="orange")),
        yaxis2=dict(title=dict(text="收盤價", font=dict(color="orange")), overlaying="y", side="right", tickfont=dict(color="orange")),
        height=400,
        hovermode="x unified",
        margin=dict(t=40, b=40)
    )

    fig.show()

if __name__ == "__main__":
    plot_price_interactive("2330", "data/institution.db")
