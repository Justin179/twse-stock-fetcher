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
# 其它 import 之後
from common.stock_loader import load_stock_list_with_names
from ui.sr_prev_high_on_heavy import scan_prev_high_on_heavy_from_df  # 或用 scan_prev_high_on_heavy_all

# === 盤中取價（直接用 analyze 模組的函式） ===
try:
    from analyze.analyze_price_break_conditions_dataloader import get_today_prices
except Exception:
    try:
        from analyze_price_break_conditions_dataloader import get_today_prices
    except Exception:
        get_today_prices = None  # 仍可 fallback 到 DB 最新收盤


def get_stock_name_by_id(stock_id: str) -> str:
    """
    從 load_stock_list_with_names() 取得的顯示字串中，找出指定代碼的名稱。
    顯示字串通常長得像：'2330 台積電' 或 '1101 台泥'。
    """
    try:
        _, stock_display = load_stock_list_with_names(refresh=False)
        for s in stock_display:
            parts = s.split()
            if parts and parts[0] == stock_id:
                return " ".join(parts[1:]) if len(parts) > 1 else ""
    except Exception:
        pass
    return ""

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
    gap_type: str          # "up" / "down" / "hv_red" / "hv_green" / "hv_true_red" / "hv_true_green"
    edge_price: float
    role: str              # "support" / "resistance" / "at_edge"
    ka_key: str
    kb_key: str
    gap_low: float         # 對 heavy SR，=edge_price
    gap_high: float        # 對 heavy SR，=edge_price
    gap_width: float       # 對 heavy SR，=0.0
    strength: str = "secondary"  # "primary"=一級加粗, "secondary"=一般


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


# =============================
# 模組化：大量 / 比昨價 / 今價 判斷（新）
# =============================
def enrich_kbar_signals(df: pd.DataFrame,
                        ma_window: int = 20,
                        heavy_ma_multiple: float = 1.7,
                        heavy_prev_multiple: float = 1.5,
                        no_shrink_ratio: float = 0.6) -> pd.DataFrame:
    """
    回傳含以下欄位的 DataFrame：
      - v_maN: 近 N 日均量
      - prev_volume: 前一根量
      - is_heavy_ma: 量 >= 近 N 日均量 * heavy_ma_multiple 且 量 >= prev_volume * no_shrink_ratio
      - is_heavy_prev: 量 >= 前一根 * heavy_prev_multiple
      - is_heavy: is_heavy_ma or is_heavy_prev

      - prev_close: 前一根收盤
      - up_vs_prev / down_vs_prev: 比昨價漲/跌
      - up_today / down_today: 今價漲/跌
      - is_true_red / is_true_green: 真紅/真綠（比昨 + 今日同向）
    """
    d = df.copy()

    # 均量與前一根量
    d["v_maN"] = d["volume"].rolling(window=ma_window, min_periods=ma_window).mean()
    d["prev_volume"] = d["volume"].shift(1)

    # 條件1：均量倍數 + 不量縮（kb >= 0.6 * ka）
    cond_ma = (d["v_maN"].notna()) & (d["volume"] >= heavy_ma_multiple * d["v_maN"])
    cond_no_shrink = d["prev_volume"].notna() & (d["volume"] >= no_shrink_ratio * d["prev_volume"])
    d["is_heavy_ma"] = cond_ma & cond_no_shrink

    # 條件2：相對前一根倍數
    d["is_heavy_prev"] = d["prev_volume"].notna() & (d["volume"] >= heavy_prev_multiple * d["prev_volume"])

    # 帶大量（任一成立）
    d["is_heavy"] = d["is_heavy_ma"] | d["is_heavy_prev"]

    # 價格關係
    d["prev_close"] = d["close"].shift(1)
    d["up_vs_prev"] = d["prev_close"].notna() & (d["close"] > d["prev_close"])
    d["down_vs_prev"] = d["prev_close"].notna() & (d["close"] < d["prev_close"])
    d["up_today"] = d["close"] > d["open"]
    d["down_today"] = d["close"] < d["open"]

    d["is_true_red"] = d["up_vs_prev"] & d["up_today"]
    d["is_true_green"] = d["down_vs_prev"] & d["down_today"]

    return d


# -----------------------------
# 情況 1：大量 K 棒的 S/R（新版規則）
# -----------------------------
def scan_heavy_sr_from_df(df: pd.DataFrame, key_col: str, timeframe: str, c1: float,
                          window: int = 20,
                          multiple: float = 1.7,
                          prev_multiple: float = 1.5,
                          no_shrink_ratio: float = 0.6) -> List[Gap]:
    """
    帶大量 :=
      (volume >= 近20均量 * multiple 且 volume >= prev_volume * no_shrink_ratio)
      or (volume >= prev_volume * prev_multiple)

    四情境（均為帶大量前提）：
      a) 比昨跌 + 今跌 → 高點 = 一級加粗 壓力
      b) 比昨漲 + 今漲 → 低點 = 一級加粗 支撐；高點 = 二級一般 壓力 (成交量是大紅棒 aka價漲量增)
      c) 比昨跌 + 今漲 → 高點 = 二級一般 壓力
      d) 比昨漲 + 今跌 → 低點 = 二級一般 支撐；高點 = 二級一般 壓力 (成交量是大紅棒 aka價漲量增)

    高點一律視為壓力候選（最後依 c1 動態轉換）。
    """
    out: List[Gap] = []
    if df.empty:
        return out

    d = enrich_kbar_signals(
        df,
        ma_window=window,
        heavy_ma_multiple=multiple,
        heavy_prev_multiple=prev_multiple,
        no_shrink_ratio=no_shrink_ratio,
    )

    d = d[d["is_heavy"]].reset_index(drop=True)
    if d.empty:
        return out

    for _, r in d.iterrows():
        key_val = _fmt_key_for_tf(r[key_col], timeframe)

        up_vs_prev   = bool(r["up_vs_prev"])
        down_vs_prev = bool(r["down_vs_prev"])
        up_today     = bool(r["up_today"])
        down_today   = bool(r["down_today"])
        is_true_red   = bool(r["is_true_red"])
        is_true_green = bool(r["is_true_green"])

        high_p = float(r["high"])
        low_p  = float(r["low"])

        # 高點：永遠是壓力來源；一級加粗 = 情境 a（比昨跌＆今跌）
        high_strength = "primary" if (down_vs_prev and down_today) else "secondary"
        high_type = "hv_true_green" if is_true_green else ("hv_true_red" if is_true_red else ("hv_green" if down_today else "hv_red"))
        role_high = "support" if c1 > high_p else "resistance" if c1 < high_p else "at_edge"
        out.append(Gap(
            timeframe=timeframe,
            gap_type=high_type,
            edge_price=float(round(high_p, 3)),
            role=role_high,
            ka_key=key_val, kb_key=key_val,
            gap_low=float(round(high_p, 3)),
            gap_high=float(round(high_p, 3)),
            gap_width=0.0,
            strength=high_strength
        ))

        # 低點：情境 b/d 會加入；情境 b = 一級加粗
        add_low = False
        low_strength = "secondary"
        low_type = "hv_true_red" if is_true_red else ("hv_true_green" if is_true_green else ("hv_red" if up_today else "hv_green"))

        if up_vs_prev and up_today:      # b
            add_low = True
            low_strength = "primary"
        elif up_vs_prev and down_today:  # d
            add_low = True

        if add_low:
            role_low = "support" if c1 > low_p else "resistance" if c1 < low_p else "at_edge"
            out.append(Gap(
                timeframe=timeframe,
                gap_type=low_type,
                edge_price=float(round(low_p, 3)),
                role=role_low,
                ka_key=key_val, kb_key=key_val,
                gap_low=float(round(low_p, 3)),
                gap_high=float(round(low_p, 3)),
                gap_width=0.0,
                strength=low_strength
            ))

    return out


# -----------------------------
# 畫圖（含成交量）
# -----------------------------
def make_chart(daily: pd.DataFrame, gaps: List[Gap], c1: float,
               show_zones: bool, show_labels: bool,
               include: Dict[str, bool],
               stock_id: str = "", stock_name: str = "") -> go.Figure:
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

    fig.add_hline(
        y=c1, line_color="black", line_width=2, line_dash="dash",
        annotation_text=f"{stock_id} {stock_name}  c1 {c1:.2f}",
        annotation_position="top left"
    )

    zone_color = {"D": "rgba(66,135,245,0.18)", "W": "rgba(255,165,0,0.18)", "M": "rgba(46,204,113,0.18)"}
    line_color_role = {"support": "#16a34a", "resistance": "#dc2626", "at_edge": "#737373"}
    line_width_tf = {"D": 1.2, "W": 1.8, "M": 2.4}
    strength_mul = {"primary": 1.8, "secondary": 1.0}
    dash_role = {"support": "dot", "resistance": "solid", "at_edge": "dash"}

    for g in gaps:
        if not include.get(g.timeframe, True):
            continue
        if show_zones and (g.gap_high > g.gap_low):
            fig.add_hrect(y0=g.gap_low, y1=g.gap_high, line_width=0,
                          fillcolor=zone_color[g.timeframe], opacity=0.25, layer="below")

        base_w = line_width_tf[g.timeframe]
        lw = base_w * strength_mul.get(getattr(g, "strength", "secondary"), 1.0)

        fig.add_hline(y=g.edge_price, line_color=line_color_role[g.role],
                      line_width=lw, line_dash=dash_role[g.role])

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


def aggregate_monthly_from_daily(daily_with_today: pd.DataFrame, last_n: int = 12) -> pd.DataFrame:
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
    st.set_page_config(page_title="S/R 撐壓系統 (D/W/M)", layout="wide")
    st.title("this is money -> 支撐 / 壓力（D / W / M）")

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
        # stock_id = st.text_input("股票代碼（例：2330）", value="2330")
        # 用 on_change 模擬提交，然後自動清空
        def submit_stock_id():
            st.session_state["submitted_stock_id"] = st.session_state["stock_id_input"]
            st.session_state["stock_id_input"] = ""  # 清空輸入框

        st.text_input(
            "股票代碼（例：2330）",
            key="stock_id_input",
            placeholder="例如：2330",
            on_change=submit_stock_id
        )

        # 使用者輸入完成按 Enter → submit_stock_id 被呼叫
        stock_id = st.session_state.get("submitted_stock_id", "").strip()

        last_days = st.number_input("日K 顯示天數", min_value=60, max_value=720, value=120, step=30)

        st.markdown("---")
        st.caption("帶大量判斷參數")
        hv_ma_mult = st.number_input("近20日均量倍數（條件1）", min_value=1.0, max_value=5.0, value=1.7, step=0.1)
        no_shrink_ratio = st.number_input("不量縮下限（kb >= ka × ?）", min_value=0.1, max_value=1.0, value=0.6, step=0.05)
        hv_prev_mult = st.number_input("相對前一根倍數（條件2）", min_value=1.0, max_value=5.0, value=1.2, step=0.1)

        st.markdown("---")
        st.caption("Pivot High 參數設定")
        d_pivot_left = st.number_input("日K pivot_left", min_value=1, max_value=10, value=3, step=1)
        d_pivot_right = st.number_input("日K pivot_right", min_value=1, max_value=10, value=3, step=1)
        w_pivot_left = st.number_input("週K pivot_left", min_value=1, max_value=10, value=2, step=1)
        w_pivot_right = st.number_input("週K pivot_right", min_value=1, max_value=10, value=2, step=1)
        m_pivot_left = st.number_input("月K pivot_left", min_value=1, max_value=10, value=1, step=1)
        m_pivot_right = st.number_input("月K pivot_right", min_value=1, max_value=10, value=1, step=1)

        st.markdown("---")
        st.caption("顯示哪種時間框架的缺口")
        inc_d = st.checkbox("日線 (D)", value=True)
        inc_w = st.checkbox("週線 (W)", value=True)
        inc_m = st.checkbox("月線 (M)", value=True)

        st.markdown("---")
        c1_override = st.text_input("c1 覆寫（通常留空；僅供測試/模擬）", value="")
        c1_val: Optional[float] = float(c1_override) if c1_override.strip() else None
        db_path = st.text_input("SQLite DB 路徑", value="data/institution.db")

        show_zones = st.checkbox("顯示缺口區間 (hrect)", value=False)
        show_labels = st.checkbox("顯示邊界標籤 (edge labels)", value=False)


    stock_name = get_stock_name_by_id(stock_id)

    from pathlib import Path

    COVER_CANDIDATES = [
        "support-and-resistance-cover-image.png",
        "data/images/support-and-resistance-cover-image.png",
    ]
    cover_img = next((p for p in COVER_CANDIDATES if Path(p).exists()), None)

    if not stock_id:
        if cover_img:
            st.image(cover_img, use_container_width=True)
        else:
            st.info("請在左側輸入股票代碼（例：2330）")
        st.stop()  # 直接中止，不要進入查資料與畫圖


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

        # === 建立 year-week → 該週第一個交易日(MM-DD) 的對照（供表格友善顯示） ===
        week_first_day_map = {}
        if not daily_with_today.empty:
            _t = daily_with_today.copy()
            iso = _t["date"].dt.isocalendar()
            _t["year_week"] = iso.year.astype(str) + "-" + iso.week.map(lambda x: f"{int(x):02d}")
            week_first_day_map = (
                _t.groupby("year_week", as_index=True)["date"]
                .min()                         # 該週第一個「交易日」
                .dt.strftime("%m-%d")          # 只顯示月-日
                .to_dict()
            )

        def _augment_week_key(val: str) -> str:
            """把 'YYYY-WW' 變成 'YYYY-WW (MM-DD)'；非週格式或查不到就原樣返回。"""
            try:
                if isinstance(val, str) and val in week_first_day_map:
                    return f"{val} ({week_first_day_map[val]})"
            except Exception:
                pass
            return val


        d_gaps = scan_gaps_from_df(daily_with_today.rename(columns={"date": "key"}), key_col="key", timeframe="D", c1=c1)
        w_gaps = scan_gaps_from_df(wk, key_col="key", timeframe="W", c1=c1)
        m_gaps = scan_gaps_from_df(mo, key_col="key", timeframe="M", c1=c1)

        d_hv = scan_heavy_sr_from_df(
            daily_with_today.rename(columns={"date": "key"}), key_col="key", timeframe="D", c1=c1,
            window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio
        )
        w_hv = scan_heavy_sr_from_df(
            wk, key_col="key", timeframe="W", c1=c1,
            window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio
        )
        m_hv = scan_heavy_sr_from_df(
            mo, key_col="key", timeframe="M", c1=c1,
            window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio
        )


        # 既有：缺口 & 大量K棒 S/R 都算完了
        # d_gaps, w_gaps, m_gaps 已就緒
        # d_hv, w_hv, m_hv 已就緒

        # === 新增：日 / 週 / 月 的「帶大量前波高」 ===
        d_prev = scan_prev_high_on_heavy_from_df(
            daily_with_today.rename(columns={"date": "key"}), key_col="key", timeframe="D", c1=c1,
            window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio,
            pivot_left=d_pivot_left, pivot_right=d_pivot_right, max_lookback=120, pivot_heavy_only=True
        )
        w_prev = scan_prev_high_on_heavy_from_df(
            wk, key_col="key", timeframe="W", c1=c1,
            window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio,
            pivot_left=w_pivot_left, pivot_right=w_pivot_right, max_lookback=60, pivot_heavy_only=True
        )
        m_prev = scan_prev_high_on_heavy_from_df(
            mo, key_col="key", timeframe="M", c1=c1,
            window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio,
            pivot_left=m_pivot_left, pivot_right=m_pivot_right, max_lookback=36, pivot_heavy_only=True
        )

        # === 修改：把三個前波高的結果併進 gaps ===
        gaps = d_gaps + w_gaps + m_gaps + d_hv + w_hv + m_hv + d_prev + w_prev + m_prev


        fig = make_chart(
            daily_with_today, gaps, c1, show_zones, show_labels,
            include={"D": inc_d, "W": inc_w, "M": inc_m},
            stock_id=stock_id, stock_name=stock_name
        )

        st.plotly_chart(fig, use_container_width=True)

        # ===============================
        # 缺口 / 大量 SR 清單 + 排序提示
        # ===============================
        df_out = pd.DataFrame([g.__dict__ for g in gaps])
        if not df_out.empty:
            # ✅ 先保留一份原始（含 Pivot High）給專區用
            df_prev_source = df_out.copy()

            # ⬇️ 缺口清單要乾淨 → 過濾掉帶量前波高
            df_out = df_out[df_out["gap_type"] != "hv_prev_high"].copy()

            role_rank = {"resistance": 0, "at_edge": 1, "support": 2}
            tf_rank   = {"M": 0, "W": 1, "D": 2}
            df_out["role_rank"] = df_out["role"].map(role_rank)
            df_out["tf_rank"]   = df_out["timeframe"].map(tf_rank)

            df_out = df_out.sort_values(["role_rank", "edge_price", "tf_rank"],
                                        ascending=[True, False, True]).reset_index(drop=True)

            # 更粗、更清楚的方向符號
            df_out.insert(0, "vs_c1", np.where(df_out["edge_price"] > c1, "▲",
                                np.where(df_out["edge_price"] < c1, "▼", "●")))

            # ⚠️ 注意：這裡不用再標註 "Pivot High"，因為已經獨立到專區了

            # 插入「c1 分隔列」並重新排序到正確位置
            marker_row = {
                "timeframe":"—","gap_type":"—","edge_price":c1,"role":"at_edge",
                "ka_key":"—","kb_key":"—","gap_low":c1,"gap_high":c1,"gap_width":0.0,
                "vs_c1":"🔶 c1","role_rank":role_rank["at_edge"],"tf_rank":1,
            }
            df_out = pd.concat([df_out, pd.DataFrame([marker_row])], ignore_index=True)
            df_out = df_out.sort_values(["role_rank","edge_price","tf_rank"],
                                        ascending=[True,False,True]).reset_index(drop=True)

            
            # ⬇️ 新增：把所有提示收納進 expander
            with st.expander("📌 提示 / 規則說明", expanded=False):
                st.markdown(f"""
            - 於支撐位買進，於壓力位賣出  -> 適用於**盤整盤**，因為沒有出趨勢，所以遇壓力(高機率)不會突破，遇支撐高機率不會跌破，短進短出。
            - 右側交易適用於**趨勢盤**，追高是因為正在上漲的趨勢仍在(帶大量破壓買)，低接是因為已經止跌(帶大量破撐之後3天量縮)下跌趨勢結束)
            ---
            - **排序規則**：角色（壓力 → 交界 → 支撐） → 價位（大 → 小） → 時間框架（月 → 週 → 日）。
            - **帶大量規則**（滿足其一即視為帶大量）：
                - 條件①（均量倍數 + 不量縮）：`volume ≥ 近20日均量 × {hv_ma_mult:.2f}` 且 `volume ≥ 前一根 × {no_shrink_ratio:.2f}`  
                （對應欄位：`is_heavy_ma`）
                - 條件②（相對前一根倍數）：`volume ≥ 前一根 × {hv_prev_mult:.2f}`  
                （對應欄位：`is_heavy_prev`）
            - **帶量前波高（hv_prev_high）**：
                - 前波高 = **pivot high 且該 K 棒本身帶大量**（`pivot_heavy_only=True`）。
                - 後續再次出現**帶大量 K 棒**時觸發啟用此線（`kb_key`=觸發日期；`ka_key`=前波高日期）。
            - 其他：
                - `vs_c1` 欄位若標示 **“Pivot High”**，代表此列為「帶量前波高」。
                """)

            # 原本這行可以刪掉或保留在 expander 底下
            # st.caption("排序規則：角色（壓力→交界→支撐） → 價位（大→小） → 時間框架（月→週→日）")
            st.markdown(f"**{stock_id} {stock_name}｜現價 c1: {c1:.2f}**")
            st.subheader("缺口 & 大量K棒 S/R")
            

            cols_order = ["vs_c1","timeframe","gap_type","edge_price","role",
                          "ka_key","kb_key","gap_low","gap_high","gap_width"]
            show_df = df_out[[c for c in cols_order if c in df_out.columns]].copy()

            # 週K鍵值美化：'YYYY-WW' -> 'YYYY-WW (MM-DD)'（日/月維持原樣）
            if "ka_key" in show_df.columns:
                show_df["ka_key"] = show_df["ka_key"].apply(_augment_week_key)
            if "kb_key" in show_df.columns:
                show_df["kb_key"] = show_df["kb_key"].apply(_augment_week_key)


            # 顯示到小數後兩位（用 Styler.format 控制渲染精度）
            num_cols = [c for c in ["edge_price","gap_low","gap_high","gap_width"] if c in show_df.columns]
            fmt_map = {c: "{:.2f}" for c in num_cols}

            # 只針對 gap_type 欄位上色（擴充：包含 hv_true_*）
            def highlight_gap_type(val: str) -> str:
                v = str(val)
                if v in ("hv_green","hv_true_green"):
                    return "background-color: #e6f4ea"   # 淡綠
                if v in ("hv_red","hv_true_red"):
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
                    .map(highlight_gap_type, subset=["gap_type"])    # 只給 gap_type 欄位上色
            )

            st.dataframe(styled, height=360, use_container_width=True)

            # ===============================
            # ② 帶量前波高「專區」表格（獨立）
            # ===============================
            st.markdown("---")
            st.subheader("帶量前波高 Pivot High")

            # 用 df_prev_source，而不是 df_out
            df_prev = df_prev_source[df_prev_source["gap_type"] == "hv_prev_high"].copy()

            if df_prev.empty:
                st.info("此範圍內沒有偵測到『帶量前波高』。")
            else:
                # 角色與時間框架排序權重（時間框架：月→週→日）
                role_rank_ph = {"resistance": 0, "at_edge": 1, "support": 2}
                tf_rank_ph   = {"M": 0, "W": 1, "D": 2}

                # 排序鍵：時間框架（月→週→日） → ka_key(大到小) → 角色（壓力→交界→支撐） → 價位（大→小）
                # ka_key 都是字串（D:YYYY-MM-DD / W:YYYY-WW / M:YYYY-MM），字串倒序與時間倒序一致
                df_prev["tf_rank_ph"]   = df_prev["timeframe"].map(tf_rank_ph)
                df_prev["role_rank_ph"] = df_prev["role"].map(role_rank_ph)

                # 先插入 c1 標記列（和第一張表一致）
                marker_row_ph = {
                    "timeframe":"—","gap_type":"—","edge_price":c1,"role":"at_edge",
                    "ka_key":"—","kb_key":"—","gap_low":c1,"gap_high":c1,"gap_width":0.0,
                    "vs_c1":"🔶 c1","tf_rank_ph":tf_rank_ph["W"],"role_rank_ph":role_rank_ph["at_edge"],
                }
                df_prev = pd.concat([df_prev, pd.DataFrame([marker_row_ph])], ignore_index=True)

                # 方向符號：維持與主表一致；並加上 Pivot High 標記字樣
                df_prev["vs_c1"] = np.where(df_prev["edge_price"] > c1, "▲",
                                    np.where(df_prev["edge_price"] < c1, "▼", "●"))
                mask_prev2 = (df_prev["gap_type"] == "hv_prev_high")
                df_prev.loc[mask_prev2, "vs_c1"] = df_prev.loc[mask_prev2, "vs_c1"] + " Pivot High"

                # 依規則排序（注意 ka_key 以字串倒序達成「大到小」）
                df_prev = df_prev.sort_values(
                    by=["tf_rank_ph", "ka_key", "role_rank_ph", "edge_price"],
                    ascending=[True, False, True, False]
                ).reset_index(drop=True)

                # 欄位顯示（把 ka_key/kb_key 改名，避免誤會）
                cols_prev = ["vs_c1","timeframe","edge_price","role","ka_key","kb_key","gap_low","gap_high","gap_width"]
                show_prev = df_prev[[c for c in cols_prev if c in df_prev.columns]].copy()
                show_prev = show_prev.rename(columns={"ka_key":"pivot_key", "kb_key":"trigger_key"})

                # 週K鍵值美化：'YYYY-WW' -> 'YYYY-WW (MM-DD)'
                if "pivot_key" in show_prev.columns:
                    show_prev["pivot_key"] = show_prev["pivot_key"].apply(_augment_week_key)
                if "trigger_key" in show_prev.columns:
                    show_prev["trigger_key"] = show_prev["trigger_key"].apply(_augment_week_key)


                # 樣式：c1 黃底、數字兩位小數
                num_cols_prev = [c for c in ["edge_price","gap_low","gap_high","gap_width"] if c in show_prev.columns]
                fmt_map_prev = {c: "{:.2f}" for c in num_cols_prev}

                def highlight_c1_row_prev(row):
                    is_marker = (str(row.get("vs_c1","")) == "🔶 c1")
                    same_price = False
                    try:
                        same_price = float(row["edge_price"]) == float(c1)
                    except Exception:
                        pass
                    if is_marker or same_price:
                        return ["background-color: #fff3cd; font-weight: bold"] * len(row)
                    return [""] * len(row)

                styled_prev = (
                    show_prev
                        .style
                        .format(fmt_map_prev)
                        .apply(highlight_c1_row_prev, axis=1)
                )

                # 顯示第二張表（高度你可再調）
                st.dataframe(styled_prev, height=260, use_container_width=True)


        else:
            st.info("此範圍內未偵測到缺口或大量 K 棒 S/R。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
