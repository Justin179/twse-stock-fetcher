#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import streamlit as st


def load_daily(conn: sqlite3.Connection, stock_id: str, last_n: int = 270) -> pd.DataFrame:
    sql = f"""
        SELECT date, open, high, low, close, volume
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT {int(last_n)}
    """
    df = pd.read_sql_query(sql, conn, params=[stock_id], parse_dates=["date"])
    df = df.dropna(subset=["open","high","low","close"])
    df = df[(df["open"]>0) & (df["high"]>0) & (df["low"]>0) & (df["close"]>0)]
    df = df.sort_values("date").reset_index(drop=True)
    # 產生緊湊的字串標籤，只顯示 yy-mm-dd（例如 "25-08-20"）
    df["date_label"] = df["date"].dt.strftime("%y-%m-%d")
    return df


def load_weekly(conn: sqlite3.Connection, stock_id: str, last_n: int = 52) -> pd.DataFrame:
    sql = f"""
        SELECT year_week AS key, open, high, low, close, volume
        FROM twse_prices_weekly
        WHERE stock_id = ?
        ORDER BY year_week DESC
        LIMIT {int(last_n)}
    """
    df = pd.read_sql_query(sql, conn, params=[stock_id])
    df = df.dropna(subset=["open","high","low","close"])
    df = df[(df["open"]>0) & (df["high"]>0) & (df["low"]>0) & (df["close"]>0)]
    return df.sort_values("key").reset_index(drop=True)


def load_monthly(conn: sqlite3.Connection, stock_id: str, last_n: int = 12) -> pd.DataFrame:
    sql = f"""
        SELECT year_month AS key, open, high, low, close, volume
        FROM twse_prices_monthly
        WHERE stock_id = ?
        ORDER BY year_month DESC
        LIMIT {int(last_n)}
    """
    df = pd.read_sql_query(sql, conn, params=[stock_id])
    df = df.dropna(subset=["open","high","low","close"])
    df = df[(df["open"]>0) & (df["high"]>0) & (df["low"]>0) & (df["close"]>0)]
    return df.sort_values("key").reset_index(drop=True)


def get_c1(conn: sqlite3.Connection, stock_id: str) -> float:
    row = pd.read_sql_query(
        "SELECT close FROM twse_prices WHERE stock_id=? ORDER BY date DESC LIMIT 1",
        conn, params=[stock_id]
    )
    if row.empty or pd.isna(row.iloc[0]["close"]):
        raise RuntimeError(f"找不到 {stock_id} 的最新收盤價（twse_prices）。")
    return float(row.iloc[0]["close"])


@dataclass
class Gap:
    timeframe: str
    gap_type: str
    edge_price: float
    role: str
    ka_key: str
    kb_key: str
    gap_low: float
    gap_high: float
    gap_width: float



def _fmt_key_for_tf(val, timeframe: str) -> str:
    if timeframe == "D":
        try:
            return pd.to_datetime(val).strftime("%Y-%m-%d")
        except Exception:
            s = str(val)
            return s[:10] if len(s) >= 10 else s
    return str(val)

def scan_gaps_from_df(df: pd.DataFrame, key_col: str, timeframe: str, c1: float) -> List[Gap]:
    out: List[Gap] = []
    if len(df) < 2:
        return out
    for i in range(1, len(df)):
        ka = df.iloc[i-1]
        kb = df.iloc[i]
        ka_low, ka_high = float(ka["low"]), float(ka["high"])
        kb_low, kb_high = float(kb["low"]), float(kb["high"])

        if ka_high < kb_low:  # up gap
            gap_low, gap_high = ka_high, kb_low
            edge, gtype = ka_high, "up"           # 下緣支撐：採 ka.high
        elif ka_low > kb_high:  # down gap
            gap_low, gap_high = kb_high, ka_low
            edge, gtype = ka_low, "down"          # 上緣壓力：採 ka.low（修正重點）
        else:
            continue

        role = "support" if c1 > edge else "resistance" if c1 < edge else "at_edge"
        out.append(Gap(timeframe, gtype, float(round(edge, 3)), role,
                       _fmt_key_for_tf(ka[key_col], timeframe), _fmt_key_for_tf(kb[key_col], timeframe),
                       float(round(gap_low,3)), float(round(gap_high,3)),
                       float(round(gap_high-gap_low,3))))
    return out


def make_chart(daily: pd.DataFrame, gaps: List[Gap], c1: float,
               show_zones: bool, show_labels: bool,
               include: Dict[str, bool]) -> go.Figure:
    fig = go.Figure()
    # 以字串類別 X 軸避免非交易日空白；並把 K 棒顏色改成 台股習慣：漲=紅、跌=綠
    fig.add_trace(go.Candlestick(
        x=daily["date_label"],
        open=daily["open"], high=daily["high"],
        low=daily["low"], close=daily["close"],
        name="Daily",
        increasing_line_color="red", increasing_fillcolor="red",
        decreasing_line_color="green", decreasing_fillcolor="green",
    ))

    fig.add_hline(y=c1, line_color="black", line_width=2, line_dash="dash",
                  annotation_text=f"c1 {c1}", annotation_position="top left")

    zone_color = {"D": "rgba(66,135,245,0.18)", "W": "rgba(255,165,0,0.18)", "M": "rgba(46,204,113,0.18)"}
    line_color_role = {"support": "#16a34a", "resistance": "#dc2626", "at_edge": "#737373"}
    line_width_tf = {"D": 1.2, "W": 1.8, "M": 2.4}
    dash_role = {"support": "dot", "resistance": "solid", "at_edge": "dash"}

    for g in gaps:
        if not include.get(g.timeframe, True):
            continue
        if show_zones:
            fig.add_hrect(y0=g.gap_low, y1=g.gap_high, line_width=0,
                          fillcolor=zone_color[g.timeframe], opacity=0.25, layer="below")
        fig.add_hline(y=g.edge_price, line_color=line_color_role[g.role],
                      line_width=line_width_tf[g.timeframe], line_dash=dash_role[g.role])

        if show_labels:
            fig.add_annotation(xref="paper", x=0.99, xanchor="right",
                               y=g.edge_price, yanchor="middle",
                               text=f"{g.timeframe} {g.role} {g.edge_price} ({g.kb_key})",
                               showarrow=False, font=dict(size=10, color=line_color_role[g.role]),
                               bgcolor="rgba(255,255,255,0.6)", bordercolor="rgba(0,0,0,0.2)")

    # 僅顯示交易日（類別軸），避免節假日空白
    fig.update_xaxes(type="category")
    fig.update_layout(
        xaxis_rangeslider_visible=True,
        margin=dict(l=40, r=20, t=40, b=40),
        xaxis_title="Date (yy-mm-dd)",
        yaxis_title="Price",
        height=720,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    return fig


def main() -> None:
    st.set_page_config(page_title="Gap S/R (D/W/M)", layout="wide")
    st.title("缺口支撐 / 壓力（D / W / M）互動圖")

    with st.sidebar:
        st.subheader("設定")
        db_path = st.text_input("SQLite DB 路徑", value="data/institution.db")
        stock_id = st.text_input("股票代碼（例：2330、2317）", value="2317")
        last_days = st.number_input("日K 顯示天數", min_value=60, max_value=720, value=120, step=30)
        show_zones = st.checkbox("顯示缺口區間 (hrect)", value=False)
        show_labels = st.checkbox("顯示邊界標籤 (edge labels)", value=False)

        st.markdown("---")
        st.caption("顯示哪種時間框架的缺口")
        inc_d = st.checkbox("日線 (D)", value=True)
        inc_w = st.checkbox("週線 (W)", value=True)
        inc_m = st.checkbox("月線 (M)", value=True)

        c1_override = st.text_input("c1 覆寫（可留空）", value="")
        c1_val: Optional[float] = float(c1_override) if c1_override.strip() else None

    conn = sqlite3.connect(db_path)
    try:
        daily = load_daily(conn, stock_id, last_n=int(last_days))
        if daily.empty:
            st.error("查無日K資料。")
            return
        c1 = c1_val if c1_val is not None else get_c1(conn, stock_id)

        d_gaps = scan_gaps_from_df(daily.rename(columns={"date":"key"}), key_col="key", timeframe="D", c1=c1)
        wk = load_weekly(conn, stock_id, last_n=52)
        mo = load_monthly(conn, stock_id, last_n=12)
        w_gaps = scan_gaps_from_df(wk, key_col="key", timeframe="W", c1=c1)
        m_gaps = scan_gaps_from_df(mo, key_col="key", timeframe="M", c1=c1)
        gaps = d_gaps + w_gaps + m_gaps

        fig = make_chart(daily, gaps, c1, show_zones, show_labels, include={"D": inc_d, "W": inc_w, "M": inc_m})
        st.plotly_chart(fig, use_container_width=True)

        df_out = pd.DataFrame([g.__dict__ for g in gaps])
        if not df_out.empty:
            role_rank = {"resistance": 0, "support": 1, "at_edge": 2}
            tf_rank = {"M": 0, "W": 1, "D": 2}
            df_out["role_rank"] = df_out["role"].map(role_rank)
            df_out["tf_rank"] = df_out["timeframe"].map(tf_rank)
            # 排序：角色 → 新近度(kb_key 由新到舊) → 時間框架
            df_out = df_out.sort_values(["role_rank", "edge_price", "tf_rank"], ascending=[True, False, True]) \
               .drop(columns=["role_rank", "tf_rank"])
            st.subheader("缺口清單")
            st.dataframe(df_out, height=360, use_container_width=True)
        else:
            st.info("此範圍內未偵測到缺口。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
