#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# === 盤中取價（直接用 analyze 模組的函式） ===
try:
    # 正常專案結構：src/analyze/analyze_price_break_conditions_dataloader.py
    from analyze.analyze_price_break_conditions_dataloader import get_today_prices
except Exception:
    # 若 PYTHONPATH 設定不同，退而求其次嘗試同目錄匯入
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
    # 保留供對照 DB 週K用（實際圖表改用動態聚合）
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
    # 保留供對照 DB 月K用（實際圖表改用動態聚合）
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
# 缺口掃描
# -----------------------------
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
            edge, gtype = ka_high, "up"           # 下緣支撐（採 ka.high）
        elif ka_low > kb_high:  # down gap
            gap_low, gap_high = kb_high, ka_low
            edge, gtype = ka_low, "down"          # 上緣壓力（採 ka.low）
        else:
            continue

        role = "support" if c1 > edge else "resistance" if c1 < edge else "at_edge"
        out.append(Gap(timeframe, gtype, float(round(edge, 3)), role,
                       _fmt_key_for_tf(ka[key_col], timeframe), _fmt_key_for_tf(kb[key_col], timeframe),
                       float(round(gap_low,3)), float(round(gap_high,3)),
                       float(round(gap_high-gap_low,3))))
    return out


# -----------------------------
# 畫圖（含成交量）
# -----------------------------
def make_chart(daily: pd.DataFrame, gaps: List[Gap], c1: float,
               show_zones: bool, show_labels: bool,
               include: Dict[str, bool]) -> go.Figure:
    fig = go.Figure()

    # K 線（主 y 軸）
    fig.add_trace(go.Candlestick(
        x=daily["date_label"],
        open=daily["open"], high=daily["high"],
        low=daily["low"], close=daily["close"],
        name="Daily",
        increasing_line_color="red", increasing_fillcolor="red",
        decreasing_line_color="green", decreasing_fillcolor="green",
        yaxis="y1"
    ))

    # 成交量（副 y 軸，灰色透明 bar）— hover 只顯示「張」
    fig.add_trace(go.Bar(
        x=daily["date_label"],
        y=daily["volume"],                     # 這裡是「股」
        name="Volume",
        marker=dict(color="rgba(128,128,128,0.35)"),
        yaxis="y2",
        customdata=(daily["volume"] / 1000.0), # 轉成「張」提供給 tooltip
        hovertemplate="Volume: %{customdata:,.0f} 張<extra></extra>"
    ))

    # 現價水平線
    fig.add_hline(y=c1, line_color="black", line_width=2, line_dash="dash",
                  annotation_text=f"c1 {c1}", annotation_position="top left")

    # 缺口可視化
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
            fig.add_annotation(xref="paper", x=0.995, xanchor="right",
                               y=g.edge_price, yanchor="middle",
                               text=f"{g.timeframe} {g.role} {g.edge_price} ({g.kb_key})",
                               showarrow=False, font=dict(size=10, color=line_color_role[g.role]),
                               bgcolor="rgba(255,255,255,0.6)", bordercolor="rgba(0,0,0,0.2)")

    # 類別 X 軸避免假日空白；雙 y 軸設定
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
    """
    - 若 today.date 尚未入庫：新增一列（用 API 的 o/h/l/c1/v）
    - 若 today.date 已存在：覆寫該日 O/H/L/C/V
    - 僅在記憶體合併，不寫入 DB
    """
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
    vol = _safe_float(today, "v", default=0.0)

    # ★ 盤中 v 是「張」，DB volume 是「股」→ 統一轉成股
    if vol is not None:
        vol = float(vol) * 1000.0

    row_today = {
        "date": t_date,
        "open": o, "high": h, "low": l, "close": c1,
        "volume": vol,                           # 已換成「股」
        "date_label": t_date.strftime("%y-%m-%d"),
    }

    df = daily.copy()
    mask_same_day = (df["date"].dt.normalize() == t_date)
    if mask_same_day.any():
        idx = df.index[mask_same_day][-1]
        for k, v in row_today.items():
            df.at[idx, k] = v
    else:
        df = pd.concat([df, pd.DataFrame([row_today])], ignore_index=True)

    return df.sort_values("date").reset_index(drop=True)


def aggregate_weekly_from_daily(daily_with_today: pd.DataFrame, last_n: int = 52) -> pd.DataFrame:
    """以日K（含今天）動態聚合週K（ISO 週）"""
    if daily_with_today.empty:
        return pd.DataFrame(columns=["key", "open", "high", "low", "close", "volume"])
    df = daily_with_today.copy()
    df["date"] = pd.to_datetime(df["date"])
    iso = df["date"].dt.isocalendar()
    df["year_week"] = iso.year.astype(str) + "-" + iso.week.map(lambda x: f"{int(x):02d}")
    wk = (
        df.sort_values("date")
          .groupby("year_week", as_index=False)
          .agg(
              open=("open", "first"),
              high=("high", "max"),
              low =("low",  "min"),
              close=("close","last"),
              volume=("volume","sum"),
          )
          .rename(columns={"year_week": "key"})
          .sort_values("key")
          .reset_index(drop=True)
    )
    if last_n is not None:
        wk = wk.tail(int(last_n)).reset_index(drop=True)
    return wk


def aggregate_monthly_from_daily(daily_with_today: pd.DataFrame, last_n: int = 12) -> pd.DataFrame:
    """以日K（含今天）動態聚合月K（YYYY-MM）"""
    if daily_with_today.empty:
        return pd.DataFrame(columns=["key", "open", "high", "low", "close", "volume"])
    df = daily_with_today.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    mk = (
        df.sort_values("date")
          .groupby("year_month", as_index=False)
          .agg(
              open=("open", "first"),
              high=("high", "max"),
              low =("low",  "min"),
              close=("close","last"),
              volume=("volume","sum"),
          )
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

    # === Sidebar 寬度：縮窄 ===
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
        db_path = st.text_input("SQLite DB 路徑", value="data/institution.db")
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

    conn = sqlite3.connect(db_path)
    try:
        daily = load_daily(conn, stock_id, last_n=int(last_days))
        if daily.empty:
            st.error("查無日K資料。")
            return

        # 先取富邦盤中 today（含 o/h/l/c1/c2/v），失敗則 None
        today_info = None
        if get_today_prices is not None:
            try:
                today_info = get_today_prices(stock_id, sdk=None)
            except Exception:
                today_info = None

        # c1 優先順序：UI 覆寫 > 富邦盤中 > DB 最新收盤
        if c1_val is not None:
            c1 = c1_val
        elif today_info and ("c1" in today_info):
            c1 = float(today_info["c1"])
        else:
            c1 = get_c1(conn, stock_id)

        # 把「今天盤中」併入 daily（形成最新日K；只在記憶體）
        daily_with_today = attach_intraday_to_daily(daily, today_info or {})

        # 用「含今天」的日K動態聚合 週/月K
        wk = aggregate_weekly_from_daily(daily_with_today, last_n=52)
        mo = aggregate_monthly_from_daily(daily_with_today, last_n=12)

        # 缺口掃描（皆用含今天的資料）
        d_gaps = scan_gaps_from_df(
            daily_with_today.rename(columns={"date": "key"}),
            key_col="key", timeframe="D", c1=c1
        )
        w_gaps = scan_gaps_from_df(wk, key_col="key", timeframe="W", c1=c1)
        m_gaps = scan_gaps_from_df(mo, key_col="key", timeframe="M", c1=c1)
        gaps = d_gaps + w_gaps + m_gaps

        # 作圖（含成交量）
        fig = make_chart(
            daily_with_today, gaps, c1,
            show_zones, show_labels,
            include={"D": inc_d, "W": inc_w, "M": inc_m}
        )
        st.plotly_chart(fig, use_container_width=True)

        # 缺口清單 + 排序提示
        df_out = pd.DataFrame([g.__dict__ for g in gaps])
        if not df_out.empty:
            # 角色排名：壓力 → 交界 → 支撐
            role_rank = {"resistance": 0, "at_edge": 1, "support": 2}
            tf_rank = {"M": 0, "W": 1, "D": 2}
            df_out["role_rank"] = df_out["role"].map(role_rank)
            df_out["tf_rank"]   = df_out["timeframe"].map(tf_rank)
            df_out = df_out.sort_values(
                ["role_rank", "edge_price", "tf_rank"],
                ascending=[True, False, True]
            ).drop(columns=["role_rank", "tf_rank"])

            st.subheader("缺口清單")
            st.caption("排序規則：角色（壓力→交界→支撐） → 價位（大→小） → 時間框架（月→週→日）")
            st.dataframe(df_out, height=360, use_container_width=True)
        else:
            st.info("此範圍內未偵測到缺口。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
