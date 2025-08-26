#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import numpy as np  # for vs_c1 / c1 marker row

# === 盤中取價（直接用 analyze 模組的函式） ===
try:
    from analyze.analyze_price_break_conditions_dataloader import get_today_prices
except Exception:
    try:
        from analyze_price_break_conditions_dataloader import get_today_prices
    except Exception:
        get_today_prices = None  # 仍可 fallback 到 DB 最新收盤


# -----------------------------
# 資料載入（DB）
# -----------------------------
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


# -----------------------------
# 通用資料結構
# -----------------------------
@dataclass
class Gap:
    timeframe: str
    gap_type: str          # "up" / "down" / "hv_red" / "hv_green"
    edge_price: float
    role: str              # "support" / "resistance" / "at_edge"
    ka_key: str
    kb_key: str
    gap_low: float         # 對 heavy SR，=edge_price
    gap_high: float        # 對 heavy SR，=edge_price
    gap_width: float       # 對 heavy SR，=0.0


def _fmt_key_for_tf(val, timeframe: str) -> str:
    if timeframe == "D":
        try:
            return pd.to_datetime(val).strftime("%Y-%m-%d")
        except Exception:
            s = str(val)
            return s[:10] if len(s) >= 10 else s
    return str(val)


# -----------------------------
# 缺口掃描（既有）
# -----------------------------
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
            edge, gtype = ka_high, "up"
        elif ka_low > kb_high:  # down gap
            gap_low, gap_high = kb_high, ka_low
            edge, gtype = ka_low, "down"
        else:
            continue

        role = "support" if c1 > edge else "resistance" if c1 < edge else "at_edge"
        out.append(Gap(timeframe, gtype, float(round(edge, 3)), role,
                       _fmt_key_for_tf(ka[key_col], timeframe), _fmt_key_for_tf(kb[key_col], timeframe),
                       float(round(gap_low,3)), float(round(gap_high,3)),
                       float(round(gap_high-gap_low,3))))
    return out


# -----------------------------
# 情況 1：大量 K 棒的 S/R
# -----------------------------
def mark_heavy_kbars(df: pd.DataFrame, window: int = 10, multiple: float = 2.0) -> pd.DataFrame:
    d = df.copy()
    d["v_maN"] = d["volume"].rolling(window=window, min_periods=window).mean()
    d["is_heavy"] = (d["v_maN"].notna()) & (d["volume"] >= multiple * d["v_maN"])
    d["is_red"] = d["close"] >= d["open"]
    return d


def scan_heavy_sr_from_df(df: pd.DataFrame, key_col: str, timeframe: str, c1: float,
                          window: int = 10, multiple: float = 1.8) -> List[Gap]:
    out: List[Gap] = []
    if df.empty:
        return out

    d = mark_heavy_kbars(df, window=window, multiple=multiple)
    d = d[d["is_heavy"]].reset_index(drop=True)
    if d.empty:
        return out

    for _, r in d.iterrows():
        is_red = bool(r["is_red"])
        base_type = "hv_red" if is_red else "hv_green"
        edge = float(r["low"] if is_red else r["high"])
        role = "support" if c1 > edge else "resistance" if c1 < edge else "at_edge"
        key_val = _fmt_key_for_tf(r[key_col], timeframe)
        out.append(Gap(
            timeframe=timeframe,
            gap_type=base_type,
            edge_price=float(round(edge, 3)),
            role=role,
            ka_key=key_val,
            kb_key=key_val,
            gap_low=float(round(edge, 3)),
            gap_high=float(round(edge, 3)),
            gap_width=0.0
        ))
    return out


# -----------------------------
# 畫圖（含成交量）
# -----------------------------
def make_chart(daily: pd.DataFrame, gaps: List[Gap], c1: float,
               show_zones: bool, show_labels: bool,
               include: Dict[str, bool]) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=daily["date_label"],
        open=daily["open"], high=daily["high"],
        low=daily["low"], close=daily["close"],
        name="Daily",
        increasing_line_color="red", increasing_fillcolor="red",
        decreasing_line_color="green", decreasing_fillcolor="green",
        yaxis="y1"
    ))

    fig.add_trace(go.Bar(
        x=daily["date_label"],
        y=daily["volume"],                     # DB 是股
        name="Volume",
        marker=dict(color="rgba(128,128,128,0.35)"),
        yaxis="y2",
        customdata=(daily["volume"] / 1000.0), # 轉張數給 hover
        hovertemplate="Volume: %{customdata:,.0f} 張<extra></extra>"
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
        if show_zones and (g.gap_high > g.gap_low):
            fig.add_hrect(y0=g.gap_low, y1=g.gap_high, line_width=0,
                          fillcolor=zone_color[g.timeframe], opacity=0.25, layer="below")
        fig.add_hline(y=g.edge_price, line_color=line_color_role[g.role],
                      line_width=line_width_tf[g.timeframe], line_dash=dash_role[g.role])

        if show_labels:
            label_src = "HV" if g.gap_type.startswith("hv_") else g.gap_type
            fig.add_annotation(xref="paper", x=0.995, xanchor="right",
                               y=g.edge_price, yanchor="middle",
                               text=f"{g.timeframe} {label_src} {g.role} {g.edge_price} ({g.kb_key})",
                               showarrow=False, font=dict(size=10, color=line_color_role[g.role]),
                               bgcolor="rgba(255,255,255,0.6)", bordercolor="rgba(0,0,0,0.2)")

    fig.update_xaxes(type="category")
    fig.update_layout(
        xaxis=dict(domain=[0, 1]),
        yaxis=dict(title="Price", side="left", showgrid=True, position=0.0),
        yaxis2=dict(title="Volume", side="right", overlaying="y", showgrid=False, position=1.0),
        xaxis_rangeslider_visible=True,
        margin=dict(l=40, r=40, t=40, b=40),
        height=820,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    return fig


# -----------------------------
# 盤中資料併入日K / 動態聚合
# -----------------------------
def _safe_float(d: dict, key: str, default=None):
    try:
        v = d.get(key, None)
        return float(v) if v is not None else default
    except Exception:
        return default


def attach_intraday_to_daily(daily: pd.DataFrame, today: dict) -> pd.DataFrame:
    if daily.empty or not today:
        return daily

    t_date_str = str(today.get("date") or "")
    if not t_date_str:
        return daily

    t_date = pd.to_datetime(t_date_str).normalize()
    o   = _safe_float(today, "o")
    h   = _safe_float(today, "h")
    l   = _safe_float(today, "l")
    c1  = _safe_float(today, "c1")
    v   = _safe_float(today, "v", default=0.0)

    # 盤中 v 單位是張 -> 轉股
    if v is not None: v = float(v) * 1000.0

    row_today = {
        "date": t_date, "open": o, "high": h, "low": l, "close": c1,
        "volume": v, "date_label": t_date.strftime("%y-%m-%d"),
    }

    df = daily.copy()
    mask = (df["date"].dt.normalize() == t_date)
    if mask.any():
        idx = df.index[mask][-1]
        for k, vv in row_today.items():
            df.at[idx, k] = vv
    else:
        df = pd.concat([df, pd.DataFrame([row_today])], ignore_index=True)

    return df.sort_values("date").reset_index(drop=True)


def aggregate_weekly_from_daily(daily_with_today: pd.DataFrame, last_n: int = 52) -> pd.DataFrame:
    if daily_with_today.empty:
        return pd.DataFrame(columns=["key", "open", "high", "low", "close", "volume"])
    df = daily_with_today.copy()
    df["date"] = pd.to_datetime(df["date"])
    iso = df["date"].dt.isocalendar()
    df["year_week"] = iso.year.astype(str) + "-" + iso.week.map(lambda x: f"{int(x):02d}")
    wk = (
        df.sort_values("date")
          .groupby("year_week", as_index=False)
          .agg(open=("open", "first"), high=("high", "max"),
               low=("low", "min"), close=("close", "last"),
               volume=("volume", "sum"))
          .rename(columns={"year_week": "key"})
          .sort_values("key")
          .reset_index(drop=True)
    )
    if last_n is not None:
        wk = wk.tail(int(last_n)).reset_index(drop=True)
    return wk


def aggregate_monthly_from_daily(daily_with_today: pd.DataFrame, last_n: int = 12) -> pd.DataFrame:  # FIX type
    if daily_with_today.empty:
        return pd.DataFrame(columns=["key", "open", "high", "low", "close", "volume"])
    df = daily_with_today.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    mk = (
        df.sort_values("date")
          .groupby("year_month", as_index=False)
          .agg(open=("open", "first"), high=("high", "max"),
               low=("low", "min"), close=("close", "last"),
               volume=("volume", "sum"))
          .rename(columns={"year_month": "key"})
          .sort_values("key")
          .reset_index(drop=True)
    )
    if last_n is not None:
        mk = mk.tail(int(last_n)).reset_index(drop=True)
    return mk


# -----------------------------
# 主程式
# -----------------------------
def main() -> None:
    st.set_page_config(page_title="Gap S/R (D/W/M)", layout="wide")
    st.title("缺口支撐 / 壓力（D / W / M）互動圖")

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"][aria-expanded="true"]{
            min-width: 200px !important;
            max-width: 220px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.subheader("設定")
        stock_id = st.text_input("股票代碼（例：2330、2317）", value="2330")
        last_days = st.number_input("日K 顯示天數", min_value=60, max_value=720, value=120, step=30)
        show_zones = st.checkbox("顯示缺口區間 (hrect)", value=False)
        show_labels = st.checkbox("顯示邊界標籤 (edge labels)", value=False)

        st.markdown("---")
        st.caption("顯示哪種時間框架的缺口")
        inc_d = st.checkbox("日線 (D)", value=True)
        inc_w = st.checkbox("週線 (W)", value=True)
        inc_m = st.checkbox("月線 (M)", value=True)

        c1_override = st.text_input("c1 覆寫（通常留空；僅供測試/模擬）", value="")
        c1_val: Optional[float] = float(c1_override) if c1_override.strip() else None
        db_path = st.text_input("SQLite DB 路徑", value="data/institution.db")

    conn = sqlite3.connect(db_path)
    try:
        daily = load_daily(conn, stock_id, last_n=int(last_days))
        if daily.empty:
            st.error("查無日K資料。"); return

        today_info = None
        if get_today_prices is not None:
            try:
                today_info = get_today_prices(stock_id, sdk=None)
            except Exception:
                today_info = None

        if c1_val is not None:
            c1 = c1_val
        elif today_info and ("c1" in today_info):
            c1 = float(today_info["c1"])
        else:
            c1 = get_c1(conn, stock_id)

        daily_with_today = attach_intraday_to_daily(daily, today_info or {})
        wk = aggregate_weekly_from_daily(daily_with_today, last_n=52)
        mo = aggregate_monthly_from_daily(daily_with_today, last_n=12)

        d_gaps = scan_gaps_from_df(daily_with_today.rename(columns={"date": "key"}), key_col="key", timeframe="D", c1=c1)
        w_gaps = scan_gaps_from_df(wk, key_col="key", timeframe="W", c1=c1)
        m_gaps = scan_gaps_from_df(mo, key_col="key", timeframe="M", c1=c1)
        d_hv = scan_heavy_sr_from_df(daily_with_today.rename(columns={"date": "key"}), key_col="key", timeframe="D", c1=c1)
        w_hv = scan_heavy_sr_from_df(wk, key_col="key", timeframe="W", c1=c1)
        m_hv = scan_heavy_sr_from_df(mo, key_col="key", timeframe="M", c1=c1)
        gaps = d_gaps + w_gaps + m_gaps + d_hv + w_hv + m_hv

        fig = make_chart(daily_with_today, gaps, c1, show_zones, show_labels, include={"D": inc_d, "W": inc_w, "M": inc_m})
        st.plotly_chart(fig, use_container_width=True)

        # ===============================
        # 缺口 / 大量 SR 清單 + 排序提示
        # ===============================
        df_out = pd.DataFrame([g.__dict__ for g in gaps])
        if not df_out.empty:
            role_rank = {"resistance": 0, "at_edge": 1, "support": 2}
            tf_rank   = {"M": 0, "W": 1, "D": 2}
            df_out["role_rank"] = df_out["role"].map(role_rank)
            df_out["tf_rank"]   = df_out["timeframe"].map(tf_rank)

            df_out = df_out.sort_values(["role_rank", "edge_price", "tf_rank"],
                                        ascending=[True, False, True]).reset_index(drop=True)

            # 更粗、更清楚的方向符號
            df_out.insert(0, "vs_c1", np.where(df_out["edge_price"] > c1, "▲",
                                 np.where(df_out["edge_price"] < c1, "▼", "●")))

            # 插入「c1 分隔列」並重新排序到正確位置
            marker_row = {
                "timeframe":"—","gap_type":"—","edge_price":c1,"role":"at_edge",
                "ka_key":"—","kb_key":"—","gap_low":c1,"gap_high":c1,"gap_width":0.0,
                "vs_c1":"🔶 c1","role_rank":role_rank["at_edge"],"tf_rank":1,
            }
            df_out = pd.concat([df_out, pd.DataFrame([marker_row])], ignore_index=True)
            df_out = df_out.sort_values(["role_rank","edge_price","tf_rank"],
                                        ascending=[True,False,True]).reset_index(drop=True)

            st.subheader("缺口清單（含 HV 線）")
            st.caption("排序規則：角色（壓力→交界→支撐） → 價位（大→小） → 時間框架（月→週→日）")
            st.markdown(f"**現價 c1: {c1}**")



            cols_order = ["vs_c1","timeframe","gap_type","edge_price","role",
                        "ka_key","kb_key","gap_low","gap_high","gap_width"]
            show_df = df_out[[c for c in cols_order if c in df_out.columns]].copy()

            # 顯示到小數後兩位（用 Styler.format 控制渲染精度）
            num_cols = [c for c in ["edge_price","gap_low","gap_high","gap_width"] if c in show_df.columns]
            fmt_map = {c: "{:.2f}" for c in num_cols}

            # 只針對 gap_type 欄位上色
            def highlight_gap_type(val: str) -> str:
                if val == "hv_green":
                    return "background-color: #e6f4ea"   # 淡綠
                if val == "hv_red":
                    return "background-color: #fdecea"   # 淡紅
                return ""

            # c1 高亮：整列淡黃 + 粗體
            def highlight_c1_row(row):
                is_marker = (str(row.get("vs_c1","")) == "🔶 c1")
                same_price = False
                try:
                    same_price = float(row["edge_price"]) == float(c1)
                except Exception:
                    pass
                if is_marker or same_price:
                    return ["background-color: #fff3cd; font-weight: bold"] * len(row)
                return [""] * len(row)

            styled = (
                show_df
                    .style
                    .format(fmt_map)                                 # 數字兩位小數
                    .apply(highlight_c1_row, axis=1)                 # 先套整列 c1 高亮
                    .applymap(highlight_gap_type, subset=["gap_type"])  # 只給 gap_type 欄位上色
            )

            st.dataframe(styled, height=360, use_container_width=True)


        else:
            st.info("此範圍內未偵測到缺口或大量 K 棒 S/R。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
