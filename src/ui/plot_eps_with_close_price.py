import sqlite3
import pandas as pd
import plotly.graph_objects as go
import re
from datetime import datetime

def plot_eps_with_close_price(stock_id, db_path="data/institution.db"):
    # 讀取 EPS 與季收盤價
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

    # 解析 season，例如 2024Q1
    def parse_season(s):
        match = re.match(r"(\d{4})Q(\d)", s)
        return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

    df[["year", "quarter"]] = df["season"].apply(lambda x: pd.Series(parse_season(x)))
    df = df.sort_values(by=["year", "quarter"]).tail(20).copy()
    df["label"] = df["season"].apply(lambda s: s[-4:])  # 例如 24Q1

    # 計算去年全年 EPS
    current_year = datetime.now().year
    last_year = current_year - 1
    eps_last_year_df = df[(df["year"] == last_year) & (df["quarter"].isin([1, 2, 3, 4]))]
    total_eps_last_year = eps_last_year_df["eps"].sum() if not eps_last_year_df.empty else None

    # 設定 Bar 顏色（正數淡紅、負數淡綠）
    colors_eps = ["rgba(255, 0, 0, 0.6)" if val >= 0 else "rgba(56, 200, 35, 0.8)" for val in df["eps"]]

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

    # 標題加上去年 EPS
    title_text = f"{stock_name} ({stock_id}) EPS"
    if total_eps_last_year is not None:
        title_text += (
            f"（<span style='color:red'> {last_year}</span>EPS <span style='color:red'>{total_eps_last_year:.2f} </span>元）"
        )

    fig.update_layout(
        title=title_text,
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
        barmode="relative"
    )

    return fig

if __name__ == "__main__":
    import plotly.io as pio
    pio.renderers.default = "browser"
    fig = plot_eps_with_close_price("2330")
    fig.show()
