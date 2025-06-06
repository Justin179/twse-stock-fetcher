
import sqlite3
import pandas as pd
import plotly.graph_objects as go

# 參數
stock_id = "3017"
db_path = "data/institution.db"

# 讀取資料
conn = sqlite3.connect(db_path)
df = pd.read_sql_query(f"""
    SELECT * FROM holder_concentration
    WHERE stock_id = '{stock_id}'
    ORDER BY date DESC
    LIMIT 26
""", conn)
conn.close()

df = df.sort_values(by="date")
df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
df["label"] = df["date"].apply(lambda d: f"{d.month}/{d.day}")


# 上圖：收盤價 vs 籌碼集中度
fig1 = go.Figure()
fig1.add_trace(go.Scatter(
    x=df["label"], y=df["close_price"], mode="lines+markers",
    name="收盤價", marker=dict(color="red"), yaxis="y1",
    hovertemplate="收盤價：%{y:.1f}<extra></extra>"
))
fig1.add_trace(go.Scatter(
    x=df["label"], y=df["avg_shares"], mode="lines+markers",
    name="籌碼集中度", marker=dict(color="green"), yaxis="y2",
    hovertemplate="集中度：%{y:.2f} 張<extra></extra>"
))
fig1.update_layout(
    title=f"{stock_id} 收盤價 vs 籌碼集中度",
    xaxis=dict(type="category", tickangle=-45, tickfont=dict(size=12)),
    yaxis=dict(title="收盤價", side="left"),
    yaxis2=dict(title="籌碼集中度 (張)", overlaying="y", side="right"),
    showlegend=False,
    height=400,
    margin=dict(t=40, b=40),
    hovermode="x unified"
)

# 下圖：收盤價 vs 千張大戶持股比率
fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=df["label"], y=df["close_price"], mode="lines+markers",
    name="收盤價", marker=dict(color="red"), yaxis="y1",
    hovertemplate="收盤價：%{y:.1f}<extra></extra>"
))
fig2.add_trace(go.Scatter(
    x=df["label"], y=df["ratio_1000"], mode="lines+markers",
    name="千張大戶比率", marker=dict(color="blue"), yaxis="y2",
    hovertemplate="千張大戶佔比：%{y:.2f}%<extra></extra>"
))
fig2.update_layout(
    title=f"{stock_id} 收盤價 vs 千張大戶持股比率",
    xaxis=dict(type="category", tickangle=-45, tickfont=dict(size=12)),
    yaxis=dict(title="收盤價", side="left"),
    yaxis2=dict(title="千張大戶佔比 (%)", overlaying="y", side="right"),
    showlegend=False,
    height=400,
    margin=dict(t=40, b=40),
    hovermode="x unified"
)

fig1.show()
fig2.show()
