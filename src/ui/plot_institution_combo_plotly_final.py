
import sqlite3
import pandas as pd
import plotly.graph_objects as go

def plot_institution_combo_plotly(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM stock_meta WHERE stock_id = ?", (stock_id,))
    row = cursor.fetchone()
    stock_name = row[0] if row else stock_id

    df = pd.read_sql_query("""
        SELECT date, foreign_netbuy, trust_netbuy, foreign_ratio, trust_ratio
        FROM institutional_netbuy_holding
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT 60
    """, conn, params=(stock_id,))
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["label"] = df["date"].dt.strftime("%m/%d")

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=df["label"],
        y=df["foreign_netbuy"],
        name="外資買賣超",
        marker_color=["red" if v > 0 else "green" for v in df["foreign_netbuy"]],
        hovertemplate="買賣超：%{y}<extra></extra>"
    ))
    fig1.add_trace(go.Scatter(
        x=df["label"],
        y=df["foreign_ratio"],
        mode="lines+markers",
        yaxis="y2",
        line=dict(color="blue", width=2),
        marker=dict(size=6),
        name="外資持股比率",
        hovertemplate="持股比率：%{y:.2f}%<extra></extra>"
    ))
    fig1.update_layout(
        title=f"{stock_name} ({stock_id}) 外資：買賣超 + 持股比率",
        xaxis=dict(type="category", title="日期", tickfont=dict(size=12), tickangle=-45),
        yaxis=dict(title="買賣超(張)"),
        yaxis2=dict(title=dict(text="外資持股比率(%)", font=dict(color="blue")), overlaying="y", side="right",
                    tickfont=dict(color="blue")),
        showlegend=False,
        height=400,
        hovermode="x unified",
        margin=dict(t=40, b=40)
    )

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df["label"],
        y=df["trust_netbuy"],
        name="投信買賣超",
        marker_color=["red" if v > 0 else "green" for v in df["trust_netbuy"]],
        hovertemplate="買賣超：%{y}<extra></extra>"
    ))
    fig2.add_trace(go.Scatter(
        x=df["label"],
        y=df["trust_ratio"],
        mode="lines+markers",
        yaxis="y2",
        line=dict(color="purple", width=2),
        marker=dict(size=6),
        name="投信持股比率",
        hovertemplate="持股比率：%{y:.2f}%<extra></extra>"
    ))
    fig2.update_layout(
        title=f"{stock_name} ({stock_id}) 投信：買賣超 + 持股比率",
        xaxis=dict(type="category", title="日期", tickfont=dict(size=12), tickangle=-45),
        yaxis=dict(title="買賣超(張)"),
        yaxis2=dict(title=dict(text="投信持股比率(%)", font=dict(color="purple")), overlaying="y", side="right",
                    tickfont=dict(color="purple")),
        showlegend=False,
        height=400,
        hovermode="x unified",
        margin=dict(t=40, b=40)
    )

    return fig1, fig2

if __name__ == "__main__":
    fig1, fig2 = plot_institution_combo_plotly("3017", "data/institution.db")
    fig1.show()
    fig2.show()
