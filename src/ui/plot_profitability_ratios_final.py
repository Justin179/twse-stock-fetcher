
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import re

def plot_profitability_ratios_with_close_price(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    query = f"""
        SELECT season, gross_profit_margin, operating_profit_margin,
               net_income_margin, season_close_price
        FROM profitability_ratios
        WHERE stock_id = ?
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()

    if df.empty:
        raise ValueError("查無資料，請確認資料庫中是否有該股票的三率資料。")

    # 解析 season 欄位為 year, quarter，並排序
    def parse_season(s):
        match = re.match(r"(\d{4})Q(\d)", s)
        if match:
            year = int(match.group(1))
            quarter = int(match.group(2))
            return year, quarter
        return 0, 0

    df[["year", "quarter"]] = df["season"].apply(lambda x: pd.Series(parse_season(x)))
    df = df.sort_values(by=["year", "quarter"]).tail(20).copy()
    df["label"] = df["season"].apply(lambda s: s[-4:])  # 例如 2021Q4 -> 21Q4

    fig = go.Figure()

    # 季收盤價 (左側橘色 y 軸)
    fig.add_trace(go.Scatter(
        x=df["label"], y=df["season_close_price"],
        mode="lines+markers", name="季收盤價",
        marker=dict(color="orange"),
        yaxis="y1",
        hovertemplate="季收盤價：%{y:.2f}<extra></extra>"
    ))

    # 三率 (右側黑色 y 軸)
    fig.add_trace(go.Scatter(
        x=df["label"], y=df["gross_profit_margin"],
        mode="lines+markers", name="毛利率",
        marker=dict(color="blue"), yaxis="y2",
        hovertemplate="毛利率：%{y:.2f}%<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=df["label"], y=df["operating_profit_margin"],
        mode="lines+markers", name="營業利益率",
        marker=dict(color="green"), yaxis="y2",
        hovertemplate="營益率：%{y:.2f}%<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=df["label"], y=df["net_income_margin"],
        mode="lines+markers", name="稅後淨利率",
        marker=dict(color="purple"), yaxis="y2",
        hovertemplate="淨利率：%{y:.2f}%<extra></extra>"
    ))

    fig.update_layout(
        title=f"{stock_id} 三率與季收盤價（近 5 年）",
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
    stock_id = "2308"  # 可改為你要測的股票代碼
    fig = plot_profitability_ratios_with_close_price(stock_id)
    fig.show()
