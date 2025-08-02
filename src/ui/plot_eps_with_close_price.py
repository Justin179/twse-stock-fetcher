import sqlite3
import pandas as pd
import plotly.graph_objects as go
import re

def plot_eps_with_close_price(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT season, eps, season_close_price FROM profitability_ratios WHERE stock_id = ?",
        conn, params=(stock_id,)
    )

    name_row = pd.read_sql_query(
        "SELECT name FROM stock_meta WHERE stock_id = ?",
        conn, params=(stock_id,)
    )
    conn.close()

    stock_name = name_row.iloc[0]["name"] if not name_row.empty else ""

    if df.empty:
        raise ValueError("查無資料，請確認資料庫中是否有該股票的 EPS 資料。")

    # season 排序
    def parse_season(s):
        match = re.match(r"(\d{4})Q(\d)", s)
        return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

    df[["year", "quarter"]] = df["season"].apply(lambda x: pd.Series(parse_season(x)))
    df = df.sort_values(by=["year", "quarter"]).tail(20).copy()
    df["label"] = df["season"].apply(lambda s: s[-4:])  # 21Q4 這種格式

    # 柱狀圖顏色：正數紅色、負數綠色
    colors_eps = ["red" if val >= 0 else "green" for val in df["eps"]]

    fig = go.Figure()

    # EPS Bar（放在折線圖後面，不擋線）
    fig.add_trace(go.Bar(
        x=df["label"], y=df["eps"],
        marker_color=colors_eps,
        name="EPS",
        yaxis="y2",
        offsetgroup=1,
        hovertemplate="EPS：%{y:.2f}<extra></extra>"
    ))

    # 季收盤價折線圖（橘色線，放在 Bar 上層）
    fig.add_trace(go.Scattergl(
        x=df["label"], y=df["season_close_price"],
        mode="lines+markers",
        name="季收盤價",
        line=dict(color="orange", width=2),
        marker=dict(color="orange", size=8),
        yaxis="y1",
        hovertemplate="季收盤價：%{y:.2f}<extra></extra>"
    ))

    fig.update_layout(
        title=f"{stock_name} ({stock_id}) EPS",
        xaxis=dict(type="category", tickangle=-45, tickfont=dict(size=12)),
        yaxis=dict(
            title=dict(text="季收盤價", font=dict(color="orange")),
            side="left", tickfont=dict(color="orange")
        ),
        yaxis2=dict(
            title=dict(text="EPS (元)", font=dict(color="black")),
            overlaying="y", side="right", tickfont=dict(color="black"),
            zeroline=True, zerolinewidth=1, zerolinecolor='gray'
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=450,
        margin=dict(t=40, b=40),
        hovermode="x unified",
        barmode="relative"  # 讓 bar 在後面
    )

    return fig

if __name__ == "__main__":
    import plotly.io as pio
    pio.renderers.default = "browser"
    fig = plot_eps_with_close_price("2330")
    fig.show()
