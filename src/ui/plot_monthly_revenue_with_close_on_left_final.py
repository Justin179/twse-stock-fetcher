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

    colors_yoy = ["red" if val >= 0 else "green" for val in df["yoy_rate"]]
    colors_revenue = ["red" if val >= 0 else "green" for val in df["revenue"]]
    colors_mom = ["red" if val >= 0 else "green" for val in df["mom_rate"]]

    # 第一張圖：YoY + 月收盤價
    fig1 = go.Figure(data=[
        go.Bar(
            x=df["label"], y=df["yoy_rate"], marker_color=colors_yoy,
            text=df["yoy_rate"].round(1).astype(str), textposition="outside",
            name="YoY (%)", yaxis="y2",
            hovertemplate="YoY: %{y:.1f}%<extra></extra>"
        ),
        go.Scattergl(
            x=df["label"], y=df["monthly_last_close"], mode="lines+markers",
            name="月收盤價", line=dict(color="orange", width=2),
            marker=dict(color="orange", size=8),
            hovertemplate="月收盤: %{y:.1f}<extra></extra>"
        )
    ])
    fig1.update_layout(
        title=f"{full_title} 營收年增率 YoY",
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        yaxis=dict(title=dict(text="月收盤價", font=dict(color="orange")), tickfont=dict(color="orange")),
        yaxis2=dict(title="營收年增率 YoY (%)", overlaying="y", side="right"),
        showlegend=False, height=400, hovermode="x unified", margin=dict(t=40, b=40)
    )

    # 第二張圖：月營收 + 月收盤價
    fig2 = go.Figure(data=[
        go.Bar(
            x=df["label"], y=df["revenue"], marker_color=colors_revenue,
            text=df["revenue"].round(0).astype(int).astype(str), textposition="outside",
            name="月營收", yaxis="y2",
            hovertemplate="營收: %{y:.0f}<extra></extra>"
        ),
        go.Scattergl(
            x=df["label"], y=df["monthly_last_close"], mode="lines+markers",
            name="月收盤價", line=dict(color="orange", width=2),
            marker=dict(color="orange", size=8),
            hovertemplate="月收盤: %{y:.1f}<extra></extra>"
        )
    ])
    fig2.update_layout(
        title=f"{full_title} 月營收",
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        yaxis=dict(title=dict(text="月收盤價", font=dict(color="orange")), tickfont=dict(color="orange")),
        yaxis2=dict(title="月營收 (百萬)", overlaying="y", side="right"),
        showlegend=False, height=400, hovermode="x unified", margin=dict(t=40, b=40)
    )

    # 第三張圖：MoM 月增率 + 月收盤價
    fig3 = go.Figure(data=[
        go.Bar(
            x=df["label"], y=df["mom_rate"], marker_color=colors_mom,
            text=df["mom_rate"].round(1).astype(str), textposition="outside",
            name="MoM (%)", yaxis="y2",
            hovertemplate="MoM: %{y:.1f}%<extra></extra>"
        ),
        go.Scattergl(
            x=df["label"], y=df["monthly_last_close"], mode="lines+markers",
            name="月收盤價", line=dict(color="orange", width=2),
            marker=dict(color="orange", size=8),
            hovertemplate="月收盤: %{y:.1f}<extra></extra>"
        )
    ])
    fig3.update_layout(
        title=f"{full_title} 營收月增率 MoM",
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        yaxis=dict(title=dict(text="月收盤價", font=dict(color="orange")), tickfont=dict(color="orange")),
        yaxis2=dict(title="營收月增率 MoM (%)", overlaying="y", side="right"),
        showlegend=False, height=400, hovermode="x unified", margin=dict(t=40, b=40)
    )

    return fig1, fig2, fig3

if __name__ == "__main__":
    import plotly.io as pio
    pio.renderers.default = "browser"
    fig1, fig2, fig3 = plot_monthly_revenue_plotly("3017", "data/institution.db")
    fig1.show()
    fig2.show()
    fig3.show()
