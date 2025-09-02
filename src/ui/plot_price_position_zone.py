# 🔹 ui/plot_price_position_zone.py
import plotly.graph_objects as go
from ui.plot_utils_gap_pct import annotate_pct_between_levels

def plot_price_position_zone(stock_display_reversed, today_date, c1, o, c2, h, l, w1, w2, m1, m2):
    fig = go.Figure()

    # ---- 三個區塊的標籤（分類軸） ----
    lab_d = "昨日高低點"
    lab_w = "上週高低點"
    lab_m = "上月高低點"

    # ---- 各區塊的高低（確保 high ≥ low，避免傳入顛倒）----
    d_high, d_low = (max(h, l), min(h, l))
    w_high, w_low = (max(w1, w2), min(w1, w2))
    m_high, m_low = (max(m1, m2), min(m1, m2))

    zones = [
        (lab_d, d_high, d_low),
        (lab_w, w_high, w_low),
        (lab_m, m_high, m_low),
    ]

    # ---- 畫灰色區塊 ----
    for label, high, low in zones:
        fig.add_trace(go.Bar(
            y=[high - low], x=[label], base=[low], orientation="v",
            marker=dict(color="lightgray"), showlegend=False, hoverinfo="skip"
        ))
        # 高/低數字（靠左）
        fig.add_trace(go.Scatter(
            x=[label], y=[high], mode="text",
            text=[f"高 {high:.2f}"], textposition="top left",
            textfont=dict(size=14), showlegend=False, hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=[label], y=[low], mode="text",
            text=[f"低 {low:.2f}"], textposition="bottom left",
            textfont=dict(size=14), showlegend=False, hoverinfo="skip"
        ))

    # ---- 現價 / 今開 / 昨收 水平線（跨三個分類）----
    x_cats = [z[0] for z in zones]
    price_lines = [
        (c2, f"昨日收盤 {c2:.2f}", "orange", "circle"),
        (o,  f"今日開盤 {o:.2f}",   "black",  "circle"),
        (c1, f"今日收盤 {c1:.2f}", "blue",   "star"),
    ]
    for yval, name, color, symbol in price_lines:
        fig.add_trace(go.Scatter(
            x=x_cats, y=[yval]*len(x_cats),
            mode="lines+markers", name=name,
            marker=dict(color=color, symbol=symbol, size=10),
            line=dict(color=color, width=1, dash="dot"),
            showlegend=True
        ))

    # ---- 需求重點：在 c1 與「各高點」的中間標註還要漲多少% ----
    # 昨日高點用 d_high；週/月使用 w_high、m_high（等同你想用的 w2、m2）
    annotate_pct_between_levels(fig, x=lab_d, c1=c1, level=d_high)  # 昨日高點
    annotate_pct_between_levels(fig, x=lab_w, c1=c1, level=w_high) # 上週高點
    annotate_pct_between_levels(fig, x=lab_m, c1=c1, level=m_high) # 上月高點

    # （可選）加一段淡色虛線連接 c1 與各高點，更直觀
    for label, high, _low in zones:
        y0, y1 = (min(c1, high), max(c1, high))
        if y1 > y0:  # 只有未到高點時才畫
            fig.add_shape(
                type="line", xref="x", yref="y",
                x0=label, x1=label, y0=y0, y1=y1,
                line=dict(width=1, dash="dot", color="rgba(0,0,0,0.25)")
            )

    # ---- 版面 ----
    fig.update_layout(
        title=f"　　{stock_display_reversed}　今日 = "
              f"<span style='color:red'>{today_date[5:]}</span>",
        yaxis_title="股價",
        height=500,
        margin=dict(t=30, b=30),
        template="simple_white"
    )
    return fig
