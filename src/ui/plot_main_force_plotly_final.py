
import sqlite3
import pandas as pd
import plotly.graph_objects as go

def plot_main_force_charts(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM stock_meta WHERE stock_id = ?", (stock_id,))
    row = cursor.fetchone()
    stock_name = row[0] if row else stock_id    
    
    df = pd.read_sql_query("""
        SELECT date, net_buy_sell, dealer_diff, close_price
        FROM main_force_trading
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT 60
    """, conn, params=(stock_id,))
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["label"] = df["date"].dt.strftime("%#m/%#d")

    # 主力買賣超 + 收盤價圖
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=df["label"],
        y=df["close_price"],
        mode="lines+markers",
        name="收盤價",
        line=dict(color="orange", width=2),
        yaxis="y1",
        marker=dict(size=6),
        hovertemplate="收盤價：%{y}<extra></extra>"
    ))
    fig1.add_trace(go.Bar(
        x=df["label"],
        y=df["net_buy_sell"],
        name="主力買賣超",
        marker_color=["red" if v > 0 else "green" for v in df["net_buy_sell"]],
        yaxis="y2",
        hovertemplate="主力買賣超：%{y}<extra></extra>"
    ))
    fig1.update_layout(
        title=f"{stock_name} ({stock_id}) 主力買賣超",
        xaxis=dict(type="category", title="日期", tickangle=-45),
        yaxis=dict(title=dict(text="收盤價", font=dict(color="orange")), tickfont=dict(color="orange")),
        yaxis2=dict(title="主力買賣超(張)", overlaying="y", side="right"),
        height=400,
        hovermode="x unified",
        showlegend=False,
        margin=dict(t=40, b=40)
    )

    # 買賣家數差 + 收盤價圖
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["label"],
        y=df["close_price"],
        mode="lines+markers",
        name="收盤價",
        line=dict(color="orange", width=2),
        yaxis="y1",
        marker=dict(size=6),
        hovertemplate="收盤價：%{y}<extra></extra>"
    ))
    fig2.add_trace(go.Bar(
        x=df["label"],
        y=df["dealer_diff"],
        name="買賣家數差",
        marker_color=["red" if v > 0 else "green" for v in df["dealer_diff"]],
        yaxis="y2",
        hovertemplate="家數差：%{y}<extra></extra>"
    ))
    fig2.update_layout(
        title=f"{stock_name} ({stock_id}) 買賣家數差",
        xaxis=dict(type="category", title="日期", tickangle=-45),
        yaxis=dict(title=dict(text="收盤價", font=dict(color="orange")), tickfont=dict(color="orange")),
        yaxis2=dict(title="買賣家數差(家)", overlaying="y", side="right"),
        height=400,
        hovermode="x unified",
        showlegend=False,
        margin=dict(t=40, b=40)
    )

    return fig1, fig2

if __name__ == "__main__":
    import plotly.io as pio
    pio.renderers.default = "browser"    
    fig1, fig2 = plot_main_force_charts("2330")
    fig1.show()
    fig2.show()
