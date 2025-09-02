# -*- coding: utf-8 -*-
from __future__ import annotations
import plotly.graph_objects as go

def compute_rise_pct_to_level(c1: float, level: float) -> float:
    """
    回傳 c1 還需要上漲的百分比（0~）。若已在/高於目標價，回傳 0。
    公式：max(0, (level - c1) / c1)
    """
    if c1 is None or level is None:
        return 0.0
    if c1 <= 0:
        return 0.0
    return max(0.0, (float(level) - float(c1)) / float(c1))

def annotate_pct_between_levels(
    fig: go.Figure, *, x, c1: float, level: float,
    font_size: int = 12,
    bg: str = "rgba(255,255,255,0.7)",
    border: str = "rgba(0,0,0,0.15)"
) -> None:
    """
    在 x 分類上的 y = (c1 + level)/2 放上 'xx.xx%' 或 '現價已過高'。
    x 可直接給分類字串；本函式使用 xref='x', yref='y'。
    """
    if c1 is None or level is None:
        return
    y_mid = (float(c1) + float(level)) / 2.0
    pct = compute_rise_pct_to_level(float(c1), float(level))
    text = f"{pct*100:.2f}%" if pct > 0 else "現價已過高"

    fig.add_annotation(
        x=x, y=y_mid, xref="x", yref="y", showarrow=False,
        text=text, font=dict(size=font_size),
        bgcolor=bg, bordercolor=border, borderwidth=1
    )
