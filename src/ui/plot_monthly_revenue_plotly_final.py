import sqlite3
import pandas as pd
import plotly.graph_objects as go

def plot_monthly_revenue_plotly(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT * FROM monthly_revenue WHERE stock_id = ? ORDER BY year_month DESC LIMIT 36",
        conn, params=(stock_id,)
    )
    try:
        name_row = pd.read_sql_query(
            "SELECT name FROM stock_meta WHERE stock_id = ?", conn, params=(int(stock_id),)
        )
        stock_name = name_row.iloc[0]["name"] if not name_row.empty else ""
    except:
        stock_name = ""
    conn.close()

    if df.empty:
        return

    df = df.sort_values("year_month")
    df["label"] = df["year_month"].astype(str).apply(lambda x: f"{x[2:4]}/{x[4:6]}")
    full_title = f"{stock_name} ({stock_id})"

    colors = ["red" if val >= 0 else "green" for val in df["yoy_rate"]]
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=df["label"],
        y=df["yoy_rate"],
        marker_color=colors,
        text=df["yoy_rate"].round(1).astype(str),
        textposition="outside",
        textangle=0,
        name="",
        hovertemplate="%{x}<br>%{y:.1f}%"
    ))
    fig1.update_layout(
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        showlegend=False,
        hoverlabel=dict(font=dict(size=16)),title=f"{full_title} 月營收 YoY", yaxis_title="月營收 YoY (%)", height=400)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df["label"],
        y=df["revenue"],
        marker_color="brown",
        text=df["revenue"].round(0).astype(int).astype(str),
        textposition="outside",
        textangle=0,
        name="",
        hovertemplate="%{x}<br>%{y:.0f}"
    ))
    fig2.update_layout(
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        showlegend=False,
        hoverlabel=dict(font=dict(size=16)),title=f"{full_title} 月營收", yaxis_title="月營收 (百萬)", height=400)

    return fig1, fig2

if __name__ == "__main__":
    fig1, fig2 = plot_monthly_revenue_plotly("3017", "data/institution.db")
    fig1.show()
    fig2.show()