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

    # === 第一張圖：YoY + 月收盤價 ===
    fig1 = go.Figure()

    # 主 Y 軸：YoY
    fig1.add_trace(go.Bar(
        x=df["label"],
        y=df["yoy_rate"],
        marker_color=colors,
        text=df["yoy_rate"].round(1).astype(str),
        textposition="outside",
        name="YoY (%)",
        hovertemplate="%{x}<br>%{y:.1f}%"
    ))

    # 副 Y 軸：月收盤價（藍色折線）
    fig1.add_trace(go.Scatter(name="", showlegend=False, hoverinfo="skip",
        x=df["label"],
        y=df["monthly_last_close"],
        mode="lines+markers",
        yaxis="y2",
        
        line=dict(color="orange"),
        marker=dict(color="orange"),
        hovertemplate="%{x}<br>月收盤: %{y:.1f}"
    ))

    fig1.update_layout(
        title=f"{full_title} 月營收 YoY",
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        yaxis=dict(title="月營收 YoY (%)"),
        yaxis2=dict(
            title=dict(text="月收盤價", font=dict(color="orange")),
            tickfont=dict(color="orange"),
            overlaying="y",
            side="right",
            showgrid=False
        ),
        showlegend=False,
        height=400
    )

    # === 第二張圖：營收 + 月收盤價 ===
    fig2 = go.Figure()

    fig2.add_trace(go.Bar(
        x=df["label"],
        y=df["revenue"],
        marker_color="brown",
        text=df["revenue"].round(0).astype(int).astype(str),
        textposition="outside",
        name="月營收",
        hovertemplate="%{x}<br>%{y:.0f}"
    ))

    fig2.add_trace(go.Scatter(name="", showlegend=False, hoverinfo="skip",
        x=df["label"],
        y=df["monthly_last_close"],
        mode="lines+markers",
        yaxis="y2",
        
        line=dict(color="orange"),
        marker=dict(color="orange"),
        hovertemplate="%{x}<br>月收盤: %{y:.1f}"
    ))

    fig2.update_layout(
        title=f"{full_title} 月營收",
        xaxis=dict(tickfont=dict(size=14), tickangle=-45),
        yaxis=dict(title="月營收 (百萬)"),
        yaxis2=dict(
            title=dict(text="月收盤價", font=dict(color="orange")),
            tickfont=dict(color="orange"),
            overlaying="y",
            side="right",
            showgrid=False
        ),
        showlegend=False,
        height=400
    )

    return fig1, fig2

if __name__ == "__main__":
    fig1, fig2 = plot_monthly_revenue_plotly("3017", "data/institution.db")
    fig1.show()
    fig2.show()
