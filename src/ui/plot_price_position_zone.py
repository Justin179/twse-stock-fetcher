# 🔹 ui/plot_price_position_zone.py
import plotly.graph_objects as go


def plot_price_position_zone(today_date, c1, o, c2, h, l, w1, w2, m1, m2):
    fig = go.Figure()

    # 灰色區間條
    zones = [
        ("昨日高低點", h, l),
        ("上週高低點", w1, w2),
        ("上月高低點", m1, m2)
    ]

    for label, high, low in zones:
        fig.add_trace(go.Bar(
            y=[high - low],
            x=[label],
            base=[low],
            orientation='v',
            marker=dict(color='lightgray'),
            showlegend=False,
            hoverinfo='skip'
        ))

        # 高低點標示文字靠左 + 加大
        fig.add_trace(go.Scatter(
            y=[high], x=[label],
            mode='text',
            text=[f"高 {high:.2f}"],
            textposition='top left',
            textfont=dict(size=14),
            showlegend=False,
            hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            y=[low], x=[label],
            mode='text',
            text=[f"低 {low:.2f}"],
            textposition='bottom left',
            textfont=dict(size=14),
            showlegend=False,
            hoverinfo='skip'
        ))

    # 畫出 現價 / 今開 / 昨收 三條水平線（不加文字）
    price_lines = [
        (c2, f"昨日收盤 {c2:.2f}", 'orange', 'circle'),
        (o, f"今日開盤 {o:.2f}", 'black', 'circle'),
        (c1, f"今日收盤 {c1:.2f}", 'blue', 'star')
    ]

    for yval, name, color, symbol in price_lines:
        fig.add_trace(go.Scatter(
            x=[z[0] for z in zones],
            y=[yval] * len(zones),
            mode='lines+markers',
            name=name,
            marker=dict(color=color, symbol=symbol, size=10),
            line=dict(color=color, width=1, dash='dot'),
            showlegend=True
        ))

    fig.update_layout(
        title=f"              今日: {today_date[5:]}",
        yaxis_title="股價",
        height=500,
        margin=dict(t=30, b=30),
        template="simple_white"
    )

    return fig
