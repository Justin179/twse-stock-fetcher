
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import re

def plot_profitability_ratios_with_close_price(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT season, gross_profit_margin, operating_profit_margin, net_income_margin, season_close_price FROM profitability_ratios WHERE stock_id = ?",
        conn, params=(stock_id,)
    )

    name_row = pd.read_sql_query(
        "SELECT name FROM stock_meta WHERE stock_id = ?",
        conn, params=(stock_id,)
    )
    conn.close()

    stock_name = name_row.iloc[0]["name"] if not name_row.empty else ""

    if df.empty:
        raise ValueError("查無資料，請確認資料庫中是否有該股票的三率資料。")

    # 解析 season
    def parse_season(s):
        match = re.match(r"(\d{4})Q(\d)", s)
        return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

    df[["year", "quarter"]] = df["season"].apply(lambda x: pd.Series(parse_season(x)))
    df = df.sort_values(by=["year", "quarter"]).tail(20).copy()
    df["label"] = df["season"].apply(lambda s: s[-4:])  # e.g., 21Q4

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["label"], y=df["season_close_price"],
        mode="lines+markers", name="季收盤價", marker=dict(color="orange"), yaxis="y1",
        hovertemplate="季收盤價：%{y:.2f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=df["label"], y=df["gross_profit_margin"],
        mode="lines+markers", name="毛利率", marker=dict(color="blue"), yaxis="y2",
        hovertemplate="毛利率：%{y:.2f}%<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=df["label"], y=df["operating_profit_margin"],
        mode="lines+markers", name="營業利益率", marker=dict(color="green"), yaxis="y2",
        hovertemplate="營益率：%{y:.2f}%<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=df["label"], y=df["net_income_margin"],
        mode="lines+markers", name="稅後淨利率", marker=dict(color="purple"), yaxis="y2",
        hovertemplate="淨利率：%{y:.2f}%<extra></extra>"
    ))

    fig.update_layout(
        title=f"{stock_name} ({stock_id}) 三率",
        xaxis=dict(type="category", tickangle=-45, tickfont=dict(size=12)),
        yaxis=dict(
            title=dict(text="季收盤價", font=dict(color="orange")),
            side="left", tickfont=dict(color="orange")
        ),
        yaxis2=dict(
            title=dict(text="三率 (%)", font=dict(color="black")),
            overlaying="y", side="right", tickfont=dict(color="black")
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=450,
        margin=dict(t=40, b=40),
        hovermode="x unified"
    )

    return fig

if __name__ == "__main__":
    # For testing purposes, you can run this script directly
    import plotly.io as pio
    pio.renderers.default = "browser"
    fig = plot_profitability_ratios_with_close_price("2308")
    fig.show()
