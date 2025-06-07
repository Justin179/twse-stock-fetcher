import sqlite3
import pandas as pd
import plotly.graph_objects as go

def plot_monthly_revenue_plotly(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)

    # 讀取月營收資料
    df = pd.read_sql_query(
        """
        SELECT * FROM monthly_revenue
        WHERE stock_id = ?
        ORDER BY year_month DESC
        LIMIT 36
        """, conn, params=(stock_id,)
    )

    # 讀取股票名稱
    try:
        name_row = pd.read_sql_query(
            "SELECT name FROM stock_meta WHERE stock_id = ?", conn, params=(int(stock_id),)
        )
        stock_name = name_row.iloc[0]["name"] if not name_row.empty else ""
    except:
        stock_name = ""

    conn.close()

    if df.empty:
        print(f"⚠️ 無資料: {stock_id}")
        return

    df = df.sort_values("year_month")
    df["label"] = df["year_month"].astype(str).str[:4] + "/" + df["year_month"].astype(str).str[4:]

    full_title = f"{stock_name} ({stock_id})"

    # 年增率圖
    colors = ["red" if val >= 0 else "green" for val in df["yoy_rate"]]
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=df["label"],
        y=df["yoy_rate"],
        marker_color=colors,
        text=df["yoy_rate"].round(1).astype(str),
        textposition="outside",
        textangle=0,
        name="年增率 (%)"
    ))
    fig1.update_layout(
        title=f"{full_title} 年增率",
        yaxis_title="年增率 (%)",
        height=400,
        margin=dict(t=40, b=40),
        uniformtext_minsize=10,
        uniformtext_mode="show",
    )

    # 營收圖
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df["label"],
        y=df["revenue"],
        marker_color="brown",
        text=df["revenue"].round(0).astype(int).astype(str),
        textposition="outside",
        textangle=0,
        name="營收 (百萬)"
    ))
    fig2.update_layout(
        title=f"{full_title} 營收",
        yaxis_title="營收 (百萬)",
        height=400,
        margin=dict(t=40, b=40),
        uniformtext_minsize=10,
        uniformtext_mode="show",
    )

    fig1.show()
    fig2.show()

if __name__ == "__main__":
    plot_monthly_revenue_plotly("2535")
