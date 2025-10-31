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

# 添加父目錄到 sys.path 以便正確導入模組
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from ui.price_break_display_module import (
    get_baseline_and_deduction,
    compute_ma_with_today,
)
# 其它 import 之後
from common.stock_loader import load_stock_list_with_names
from ui.sr_prev_high_on_heavy import scan_prev_high_on_heavy_from_df  # 或用 scan_prev_high_on_heavy_all
from common.login_helper import init_session_login_objects
from common.shared_stock_selector import save_selected_stock, get_last_selected_or_default, load_selected_stock
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


def get_stock_id_by_name(stock_name: str) -> str:
    """
    從 load_stock_list_with_names() 取得的顯示字串中，找出指定名稱對應的股票代碼。
    顯示字串通常長得像：'2330 台積電' 或 '1101 台泥'。
    支援部分名稱匹配，例如輸入「台積」可以找到「台積電」。
    """
    try:
        _, stock_display = load_stock_list_with_names(refresh=False)
        for s in stock_display:
            parts = s.split()
            if len(parts) >= 2:
                # 取得完整股票名稱（第二部分開始）
                full_name = " ".join(parts[1:])
                # 支援部分匹配或完全匹配
                if stock_name in full_name or full_name == stock_name:
                    return parts[0]  # 返回股票代碼
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


# -----------------------------
# 新增：量縮標記（用於關鍵價位過濾）
# -----------------------------
def _mark_volume_shrinkage(df: pd.DataFrame, 
                          ma_window: int = 20,
                          shrink_ma_ratio: float = 0.6,
                          shrink_vs_prev_ratio: float = 0.7,
                          shrink_extreme_ratio: float = 0.5) -> pd.DataFrame:
    """
    標記量縮K棒
    
    量縮定義（兩個條件任一成立即為量縮）：
    - 條件1：低於均量 + 相對前一根量縮
      is_shrink_ma = (量 <= 近20日均量 × 0.6) AND (量 <= 前一根量 × 0.7)
    - 條件2：極度量縮
      is_shrink_extreme = (量 <= 前一根量 × 0.5)
    
    回傳：添加 is_shrink 欄位的 DataFrame
    """
    d = df.copy()
    
    # 計算均量與前一根量
    d["v_ma20"] = d["volume"].rolling(window=ma_window, min_periods=ma_window).mean()
    d["prev_volume"] = d["volume"].shift(1)
    
    # 條件1：低於均量 + 相對前一根量縮
    is_shrink_ma = (
        d["v_ma20"].notna() & 
        (d["volume"] <= shrink_ma_ratio * d["v_ma20"]) &
        d["prev_volume"].notna() &
        (d["volume"] <= shrink_vs_prev_ratio * d["prev_volume"])
    )
    
    # 條件2：極度量縮（≤ 50% 前一根）
    is_shrink_extreme = (
        d["prev_volume"].notna() &
        (d["volume"] <= shrink_extreme_ratio * d["prev_volume"])
    )
    
    # 量縮 = 條件1 OR 條件2
    d["is_shrink"] = is_shrink_ma | is_shrink_extreme
    
    return d


# -----------------------------
# 新增：關鍵價位掃描（價格聚集點）
# -----------------------------
def scan_key_price_levels(df: pd.DataFrame, c1: float,
                         min_high_count: int = 3,
                         min_low_count: int = 3,
                         price_tolerance_pct: float = 0.5,
                         timeframe: str = "D") -> List[Gap]:
    """
    掃描「關鍵價位」：同一價位多次成為高點或低點的聚集區
    
    參數：
    - min_high_count: 最少需要幾次成為高點才算關鍵價位（預設 3）
    - min_low_count: 最少需要幾次成為低點才算關鍵價位（預設 3）
    - price_tolerance_pct: 價格容差百分比（預設 0.5%，即 ±0.5%）
    - timeframe: 時間框架 "D"=日K, "W"=週K, "M"=月K
    
    回傳：關鍵價位的 Gap 列表（timeframe="KEY-D" / "KEY-W" / "KEY-M"）
    
    邏輯：
    - 連續多日測試同一價位 = 該價位更重要（不需要過濾）
    - 例如：連續 3 天高點都是 100，代表 100 是非常強的壓力
    - 高低點重疊 = 最強關鍵價位（箱型區間）
    - 量縮K棒排除：排除量縮K棒的高低點，提高判斷有效性
    """
    out: List[Gap] = []
    if df.empty or len(df) < 3:  # 至少需要3根K棒
        return out
    
    # 檢查是否有必要欄位（date 或 key 都可以）
    has_date_col = "date" in df.columns
    has_key_col = "key" in df.columns
    
    if not has_date_col and not has_key_col:
        return out
    
    df = df.copy()
    
    # === 排除量縮K棒：先標記量縮，再過濾 ===
    df = _mark_volume_shrinkage(df)
    
    # 只取非量縮的K棒來收集高低點
    df_valid = df[~df["is_shrink"]].copy()
    
    if df_valid.empty or len(df_valid) < 3:
        return out
    
    # 收集所有高點和低點（K棒的 high 和 low）- 只用非量縮K棒
    high_prices = [float(row["high"]) for _, row in df_valid.iterrows() if pd.notna(row.get("high"))]
    low_prices = [float(row["low"]) for _, row in df_valid.iterrows() if pd.notna(row.get("low"))]
    
    if not high_prices or not low_prices:
        return out
    
    # === 找高點聚集 ===
    high_clusters = _find_price_clusters_simple(high_prices, price_tolerance_pct, min_high_count)
    
    # === 找低點聚集 ===
    low_clusters = _find_price_clusters_simple(low_prices, price_tolerance_pct, min_low_count)
    
    # === 檢查高低點重疊（最強關鍵價位）===
    overlap_prices = _find_overlapping_clusters(high_clusters, low_clusters, price_tolerance_pct)
    
    # timeframe 標記（用於區分日/週/月）
    tf_label = f"KEY-{timeframe}"
    
    # 生成 Gap 列表
    for cluster_price, count in high_clusters:
        role = "support" if c1 > cluster_price else "resistance" if c1 < cluster_price else "at_edge"
        
        # 檢查是否為高低點重疊
        is_overlap = any(abs(cluster_price - op) / op * 100 <= price_tolerance_pct for op, _, _ in overlap_prices)
        
        if is_overlap:
            # 找出對應的低點次數
            low_count = next((lc for op, hc, lc in overlap_prices if abs(cluster_price - op) / op * 100 <= price_tolerance_pct), count)
            gap_type = f"key_overlap_{timeframe}"
            ka_key = f"{count}次高+{low_count}次低"
        else:
            gap_type = f"key_high_{timeframe}"
            ka_key = f"{count}次高"
        
        out.append(Gap(
            timeframe=tf_label,
            gap_type=gap_type,
            edge_price=float(round(cluster_price, 2)),
            role=role,
            ka_key=ka_key,
            kb_key="",
            gap_low=float(round(cluster_price, 2)),
            gap_high=float(round(cluster_price, 2)),
            gap_width=0.0,
            strength="primary"  # 關鍵價位標為一級
        ))
    
    # 只加入未重疊的低點聚集
    for cluster_price, count in low_clusters:
        # 檢查是否已經作為重疊點加入
        is_overlap = any(abs(cluster_price - op) / op * 100 <= price_tolerance_pct for op, _, _ in overlap_prices)
        
        if not is_overlap:
            role = "support" if c1 > cluster_price else "resistance" if c1 < cluster_price else "at_edge"
            out.append(Gap(
                timeframe=tf_label,
                gap_type=f"key_low_{timeframe}",
                edge_price=float(round(cluster_price, 2)),
                role=role,
                ka_key=f"{count}次低",
                kb_key="",
                gap_low=float(round(cluster_price, 2)),
                gap_high=float(round(cluster_price, 2)),
                gap_width=0.0,
                strength="primary"
            ))
    
    return out


def _find_overlapping_clusters(high_clusters: list, low_clusters: list, tolerance_pct: float) -> list:
    """
    找出高點聚集與低點聚集重疊的價位
    
    回傳: [(overlap_price, high_count, low_count), ...]
    """
    overlaps = []
    
    for high_price, high_count in high_clusters:
        for low_price, low_count in low_clusters:
            # 檢查兩個價位是否在容差範圍內
            if abs(high_price - low_price) / max(high_price, low_price) * 100 <= tolerance_pct:
                # 取平均價格作為重疊點
                overlap_price = (high_price + low_price) / 2
                overlaps.append((overlap_price, high_count, low_count))
                break  # 找到一個重疊就跳出
    
    return overlaps


def _find_price_clusters_simple(prices: list, tolerance_pct: float, min_count: int) -> list:
    """
    找出價格聚集點（簡化版，不過濾連續K棒）
    
    邏輯：
    - 連續測試同一價位 = 該價位更重要
    - 不需要排除連續K棒，因為連續測試本身就是重要的市場行為
    
    prices: [price1, price2, ...]
    回傳: [(cluster_price, count), ...]
    """
    if not prices:
        return []
    
    # 按價格排序（保留原始索引用於debug）
    sorted_prices = sorted(prices)
    
    clusters = []
    visited = set()
    
    for i, price in enumerate(sorted_prices):
        if i in visited:
            continue
        
        # 找出在容差範圍內的所有價位
        cluster_members = [price]
        visited.add(i)
        
        for j in range(i + 1, len(sorted_prices)):
            other_price = sorted_prices[j]
            
            # 超出容差範圍就停止
            if other_price > price * (1 + tolerance_pct / 100):
                break
            
            # 在容差範圍內，加入聚集點
            cluster_members.append(other_price)
            visited.add(j)
        
        # 如果聚集次數達標，記錄此聚集點
        if len(cluster_members) >= min_count:
            avg_price = sum(cluster_members) / len(cluster_members)
            clusters.append((avg_price, len(cluster_members)))
    
    return clusters


# -----------------------------
# 新增：均線支撐壓力掃描
# -----------------------------
def scan_ma_sr_from_stock(stock_id: str, today_date: str, c1: float) -> List[Gap]:
    """
    掃描均線支撐壓力，包含：
    1. 上彎/下彎均線：只有上彎且在現價下方的均線才算支撐，只有下彎且在現價上方的均線才算壓力
    2. 基準價與扣抵值：找距離現價最近的均線，取其基準價和扣抵值作為支撐/壓力
    """
    out: List[Gap] = []
    ma_periods = [5, 10, 24, 72]
    
    # 儲存所有均線資訊
    ma_data = {}
    
    for n in ma_periods:
        try:
            # 取得均線點位
            ma = compute_ma_with_today(stock_id, today_date, c1, n)
            # 取得基準價與扣抵值
            baseline, deduction, *_ = get_baseline_and_deduction(stock_id, today_date, n=n)
            
            if ma is not None:
                # 判斷均線上彎/下彎：使用現價 c1 vs baseline
                is_uptrending = baseline is not None and c1 > baseline
                is_downtrending = baseline is not None and c1 < baseline
                
                ma_data[n] = {
                    'ma': float(ma),
                    'baseline': baseline,
                    'deduction': deduction,
                    'is_uptrending': is_uptrending,
                    'is_downtrending': is_downtrending
                }
                
                # 1. 上彎/下彎均線的支撐壓力
                if is_uptrending and ma < c1:
                    # 上彎且在現價下方 → 支撐
                    out.append(Gap(
                        timeframe="MA",
                        gap_type=f"ma{n}_up",
                        edge_price=float(round(ma, 3)),
                        role="support",
                        ka_key=f"MA{n}",
                        kb_key=today_date,
                        gap_low=float(round(ma, 3)),
                        gap_high=float(round(ma, 3)),
                        gap_width=0.0,
                        strength="secondary"
                    ))
                elif is_downtrending and ma > c1:
                    # 下彎且在現價上方 → 壓力
                    out.append(Gap(
                        timeframe="MA",
                        gap_type=f"ma{n}_down",
                        edge_price=float(round(ma, 3)),
                        role="resistance",
                        ka_key=f"MA{n}",
                        kb_key=today_date,
                        gap_low=float(round(ma, 3)),
                        gap_high=float(round(ma, 3)),
                        gap_width=0.0,
                        strength="secondary"
                    ))
        except Exception as e:
            print(f"處理 {n} 日均線時發生錯誤: {e}")
            continue
    
    # 2. 基準價與扣抵值：找距離現價最近的均線
    if ma_data:
        # 計算每個均線與現價的距離
        distances = {n: abs(data['ma'] - c1) for n, data in ma_data.items()}
        closest_ma = min(distances.keys(), key=lambda k: distances[k])
        closest_data = ma_data[closest_ma]
        
        # 基準價的支撐/壓力
        if closest_data['baseline'] is not None:
            baseline = float(closest_data['baseline'])
            if baseline > c1:
                # 基準價在現價上方 → 壓力
                out.append(Gap(
                    timeframe="MA",
                    gap_type=f"baseline{closest_ma}",
                    edge_price=float(round(baseline, 3)),
                    role="resistance",
                    ka_key=f"基準價MA{closest_ma}",
                    kb_key=today_date,
                    gap_low=float(round(baseline, 3)),
                    gap_high=float(round(baseline, 3)),
                    gap_width=0.0,
                    strength="primary"  # 基準價設為一級加粗
                ))
            elif baseline < c1:
                # 基準價在現價下方 → 支撐
                out.append(Gap(
                    timeframe="MA",
                    gap_type=f"baseline{closest_ma}",
                    edge_price=float(round(baseline, 3)),
                    role="support",
                    ka_key=f"基準價MA{closest_ma}",
                    kb_key=today_date,
                    gap_low=float(round(baseline, 3)),
                    gap_high=float(round(baseline, 3)),
                    gap_width=0.0,
                    strength="primary"  # 基準價設為一級加粗
                ))
        
        # 扣抵值的支撐/壓力
        if closest_data['deduction'] is not None:
            deduction = float(closest_data['deduction'])
            if deduction > c1:
                # 扣抵值在現價上方 → 壓力
                out.append(Gap(
                    timeframe="MA",
                    gap_type=f"deduction{closest_ma}",
                    edge_price=float(round(deduction, 3)),
                    role="resistance",
                    ka_key=f"扣抵值MA{closest_ma}",
                    kb_key=today_date,
                    gap_low=float(round(deduction, 3)),
                    gap_high=float(round(deduction, 3)),
                    gap_width=0.0,
                    strength="primary"  # 扣抵值設為一級加粗
                ))
            elif deduction < c1:
                # 扣抵值在現價下方 → 支撐
                out.append(Gap(
                    timeframe="MA",
                    gap_type=f"deduction{closest_ma}",
                    edge_price=float(round(deduction, 3)),
                    role="support",
                    ka_key=f"扣抵值MA{closest_ma}",
                    kb_key=today_date,
                    gap_low=float(round(deduction, 3)),
                    gap_high=float(round(deduction, 3)),
                    gap_width=0.0,
                    strength="primary"  # 扣抵值設為一級加粗
                ))
    
    return out


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

    # 添加股票代碼和名稱的標記（不可見，只為了在圖例中顯示）
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(size=0, color='rgba(0,0,0,0)'),
        name=f"{stock_id} {stock_name}",
        showlegend=True,
        hoverinfo='skip'
    ))

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

    zone_color = {"D": "rgba(66,135,245,0.18)", "W": "rgba(255,165,0,0.18)", "M": "rgba(46,204,113,0.18)", "MA": "rgba(138,43,226,0.18)", 
                  "KEY-D": "rgba(255,215,0,0.25)", "KEY-W": "rgba(255,215,0,0.30)", "KEY-M": "rgba(255,215,0,0.35)"}
    line_color_role = {"support": "#16a34a", "resistance": "#dc2626", "at_edge": "#737373"}
    line_width_tf = {"D": 1.2, "W": 1.8, "M": 2.4, "MA": 2.0, 
                     "KEY-D": 2.5, "KEY-W": 2.8, "KEY-M": 3.2}
    strength_mul = {"primary": 1.8, "secondary": 1.0}
    dash_role = {"support": "dot", "resistance": "solid", "at_edge": "dash"}

    for g in gaps:
        # KEY 的 checkbox 控制所有 KEY-D, KEY-W, KEY-M
        if g.timeframe.startswith("KEY"):
            if not include.get("KEY", True):
                continue
        elif not include.get(g.timeframe, True):
            continue
            
        if show_zones and (g.gap_high > g.gap_low):
            fig.add_hrect(y0=g.gap_low, y1=g.gap_high, line_width=0,
                          fillcolor=zone_color.get(g.timeframe, "rgba(128,128,128,0.18)"), opacity=0.25, layer="below")

        base_w = line_width_tf.get(g.timeframe, 1.5)
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

    # === 新增：標註最靠近現價的支撐與壓力 ===
    # 過濾出有效的支撐與壓力
    supports = [g for g in gaps if g.role == "support" and (
        not g.timeframe.startswith("KEY") and include.get(g.timeframe, True) or
        g.timeframe.startswith("KEY") and include.get("KEY", True)
    )]
    resistances = [g for g in gaps if g.role == "resistance" and (
        not g.timeframe.startswith("KEY") and include.get(g.timeframe, True) or
        g.timeframe.startswith("KEY") and include.get("KEY", True)
    )]
    
    # 找最靠近現價的支撐（在現價下方，取最大值）
    if supports:
        nearest_support = max(supports, key=lambda g: g.edge_price)
        
        # 檢查是否有重疊的支撐（價格在容差範圍內的，不論來源）
        # 這會包含：缺口、大量K棒、關鍵價位、均線等所有類型的支撐
        overlapping_supports = [g for g in supports if abs(g.edge_price - nearest_support.edge_price) / nearest_support.edge_price * 100 <= 0.3]
        
        # 標註文字：顯示重複次數
        overlap_count = len(overlapping_supports)
        if overlap_count > 1:
            label_text = f"{nearest_support.edge_price:.2f} ({overlap_count})"  # 顯示重複次數
            font_size = 18
        else:
            label_text = f"{nearest_support.edge_price:.2f}"
            font_size = 16
        
        # 在圖上標註（綠色支撐在現價下方）
        fig.add_annotation(
            xref="paper",
            x=0.98,
            xanchor="right",
            y=nearest_support.edge_price,
            yanchor="top",  # 標註框的上邊對齊價位線
            text=label_text,
            showarrow=False,  # 移除箭頭
            font=dict(size=font_size, color='white', family='Arial Black'),
            bgcolor='rgba(22, 163, 74, 0.85)',
            bordercolor='#16a34a',
            borderwidth=3,
            borderpad=6
        )
    
    # 找最靠近現價的壓力（在現價上方，取最小值）
    if resistances:
        nearest_resistance = min(resistances, key=lambda g: g.edge_price)
        
        # 檢查是否有重疊的壓力（價格在容差範圍內的，不論來源）
        overlapping_resistances = [g for g in resistances if abs(g.edge_price - nearest_resistance.edge_price) / nearest_resistance.edge_price * 100 <= 0.3]
        
        # 標註文字：顯示重複次數
        overlap_count = len(overlapping_resistances)
        if overlap_count > 1:
            label_text = f"{nearest_resistance.edge_price:.2f} ({overlap_count})"  # 顯示重複次數
            font_size = 18
        else:
            label_text = f"{nearest_resistance.edge_price:.2f}"
            font_size = 16
        
        # 在圖上標註（紅色壓力在現價上方）
        fig.add_annotation(
            xref="paper",
            x=0.98,
            xanchor="right",
            y=nearest_resistance.edge_price,
            yanchor="bottom",  # 標註框的下邊對齊價位線
            text=label_text,
            showarrow=False,  # 移除箭頭
            font=dict(size=font_size, color='white', family='Arial Black'),
            bgcolor='rgba(220, 38, 38, 0.85)',
            bordercolor='#dc2626',
            borderwidth=3,
            borderpad=6
        )
    
    # === 新增：檢查現價是否為多個關鍵點位的交會處 ===
    # 收集所有在現價附近的關鍵點位（包含所有類型：缺口、大量K棒、關鍵價位、帶量前波高、均線）
    # 不分支撐/壓力/at_edge，只要價格在容差範圍內就計入
    all_gaps_at_c1 = [
        g for g in gaps 
        if abs(g.edge_price - c1) / c1 * 100 <= 0.3 and  # 價格容差 0.3%（與支撐/壓力重疊計算一致）
        (
            # 一般時間框架（D/W/M/MA）：檢查 checkbox 是否勾選
            (not g.timeframe.startswith("KEY") and include.get(g.timeframe, True)) or
            # 關鍵價位（KEY-D/KEY-W/KEY-M）：統一由 KEY checkbox 控制
            (g.timeframe.startswith("KEY") and include.get("KEY", True))
        )
    ]
    
    # 只要現價位置有關鍵點位匯集（>= 1個），就標註出來
    if len(all_gaps_at_c1) >= 1:
        confluence_count = len(all_gaps_at_c1)
        
        # 標註文字：顯示匯集次數（與支撐/壓力標註格式一致）
        if confluence_count > 1:
            label_text = f"{c1:.2f} ({confluence_count})"
        else:
            label_text = f"{c1:.2f}"
        
        # 根據匯集次數調整字體大小（匯集越多，字體越大）
        if confluence_count >= 5:
            font_size = 20  # 5個以上：特大
        elif confluence_count >= 3:
            font_size = 19  # 3-4個：大
        elif confluence_count >= 2:
            font_size = 18  # 2個：標準
        else:
            font_size = 16  # 1個：小
        
        # 在圖上標註（灰黑色標註，放在左側，樣式與右側紅綠標註一致）
        fig.add_annotation(
            xref="paper",
            x=0.01,  # 靠近圖表左邊緣
            xanchor="left",
            y=c1,
            yanchor="middle",  # 標註框垂直置中對齊價位線
            text=label_text,
            showarrow=False,
            font=dict(size=font_size, color='white', family='Arial Black'),
            bgcolor='rgba(80, 80, 80, 0.9)',  # 更亮的灰色背景，更明顯
            bordercolor='#606060',  # 更亮的灰色邊框
            borderwidth=3,
            borderpad=6
        )

    fig.update_xaxes(type="category")
    fig.update_layout(
        xaxis=dict(domain=[0, 1]),
        yaxis=dict(title="Price", side="left", showgrid=True, position=0.0),
        yaxis2=dict(title="Volume", side="right", overlaying="y", showgrid=False, position=1.0),
        xaxis_rangeslider_visible=True,
        margin=dict(l=40, r=40, t=40, b=40),
        height=820,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=14))
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
    v   = _safe_float(today, "v", default=None)

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
            if vv is not None: # 改成只在 vv(value) 非 None 時才覆寫DB資料
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
    st.title("this is money -> 支撐 x 壓力 x 成交量（D / W / M / 被動當沖）")

def main() -> None:
    st.set_page_config(page_title="S/R 撐壓系統 (D/W/M)", layout="wide", initial_sidebar_state="collapsed")
    st.title("this is money -> 支撐 x 壓力 x 成交量（D / W / M / 被動當沖）")

    # 🔹 智慧自動刷新：偵測 app_v4 的股票變更
    # 初始化當前股票
    if "submitted_stock_id" not in st.session_state:
        st.session_state["submitted_stock_id"] = get_last_selected_or_default(default="2330")
    
    with st.sidebar:
        st.subheader("設定")
        # stock_id = st.text_input("股票代碼（例：2330）", value="2330")
        # 用 on_change 模擬提交，然後自動清空
        def submit_stock_id():
            user_input = st.session_state["stock_id_input"].strip()
            
            # 判斷輸入是否為純數字（股票代碼）
            if user_input.isdigit():
                st.session_state["submitted_stock_id"] = user_input
            else:
                # 輸入包含中文或非純數字，嘗試作為股票名稱查詢
                stock_id = get_stock_id_by_name(user_input)
                if stock_id:
                    st.session_state["submitted_stock_id"] = stock_id
                else:
                    # 如果找不到對應的股票代碼，直接使用原輸入（可能是特殊代碼格式）
                    st.session_state["submitted_stock_id"] = user_input
            
            # 🔹 儲存選擇的股票（讓其他應用可以同步）
            save_selected_stock(st.session_state["submitted_stock_id"])
            
            st.session_state["stock_id_input"] = ""  # 清空輸入框

        # 🔹 初始化：如果還沒有 submitted_stock_id，從共享檔案讀取
        if "submitted_stock_id" not in st.session_state or not st.session_state["submitted_stock_id"]:
            st.session_state["submitted_stock_id"] = get_last_selected_or_default(default="2330")

        st.text_input(
            "股票代碼或名稱",
            key="stock_id_input",
            placeholder="例如：2330 或 台積電",
            on_change=submit_stock_id,
            help="可輸入股票代碼（如：2330）或中文名稱（如：台積電）"
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
        st.caption("關鍵價位參數設定（價格聚集點）")
        st.markdown("**日K門檻（較高，減少線條）**")
        st.session_state["key_min_high_d"] = st.number_input(
            "日K-高點聚集門檻", min_value=2, max_value=10, value=4, step=1,
            help="日K同一價位至少需要成為幾次「高點」才算關鍵壓力"
        )
        st.session_state["key_min_low_d"] = st.number_input(
            "日K-低點聚集門檻", min_value=2, max_value=10, value=4, step=1,
            help="日K同一價位至少需要成為幾次「低點」才算關鍵支撐"
        )
        st.markdown("**週K/月K門檻（標準）**")
        st.session_state["key_min_high"] = st.number_input(
            "週月K-高點聚集門檻", min_value=2, max_value=10, value=3, step=1,
            help="週K/月K同一價位至少需要成為幾次「高點」才算關鍵壓力"
        )
        st.session_state["key_min_low"] = st.number_input(
            "週月K-低點聚集門檻", min_value=2, max_value=10, value=3, step=1,
            help="週K/月K同一價位至少需要成為幾次「低點」才算關鍵支撐"
        )
        st.session_state["key_tolerance"] = st.number_input(
            "價格容差 (%)", min_value=0.1, max_value=2.0, value=0.5, step=0.1,
            help="允許的價格誤差範圍（百分比）"
        )

        st.markdown("---")
        st.caption("顯示哪種時間框架的缺口")
        inc_d = st.checkbox("日線 (D)", value=True)
        inc_w = st.checkbox("週線 (W)", value=True)
        inc_m = st.checkbox("月線 (M)", value=True)
        inc_ma = st.checkbox("均線 (MA)", value=True)
        inc_key = st.checkbox("關鍵價位 (KEY)", value=True)

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

        # 取得 session 的 sdk/dl（只會初始化一次）
        sdk, dl = init_session_login_objects()
        today_info = None
        if get_today_prices is not None:
            try:
                today_info = get_today_prices(stock_id, sdk=None)
            except Exception:
                today_info = None

        # 取得 today_date（參考 price_break_display_module 的做法）
        today_date = None
        if today_info and ("date" in today_info):
            today_date = today_info["date"]
        else:
            # fallback：取 daily_with_today 的最後一筆 date（已包含盤中合併）
            try:
                if not daily.empty:
                    # daily 尚未合併盤中，使用 daily 的最後一筆；若後面需要盤中則使用 daily_with_today
                    today_date = daily["date"].iloc[-1].strftime("%Y-%m-%d")
                else:
                    today_date = None
            except Exception:
                today_date = None

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

        # === 新增：均線支撐壓力掃描 ===
        ma_sr = scan_ma_sr_from_stock(stock_id, today_date or "", c1)

        # === 新增：關鍵價位掃描（價格聚集點）- 日/週/月K 分別掃描 ===
        key_levels_d = scan_key_price_levels(
            daily_with_today, c1,
            min_high_count=st.session_state.get("key_min_high_d", 4),  # 日K使用較高門檻
            min_low_count=st.session_state.get("key_min_low_d", 4),    # 日K使用較高門檻
            price_tolerance_pct=st.session_state.get("key_tolerance", 0.5),
            timeframe="D"
        )
        key_levels_w = scan_key_price_levels(
            wk, c1,
            min_high_count=st.session_state.get("key_min_high", 3),  # 週K使用標準門檻
            min_low_count=st.session_state.get("key_min_low", 3),    # 週K使用標準門檻
            price_tolerance_pct=st.session_state.get("key_tolerance", 0.5),
            timeframe="W"
        )
        key_levels_m = scan_key_price_levels(
            mo, c1,
            min_high_count=st.session_state.get("key_min_high", 3),  # 月K使用標準門檻
            min_low_count=st.session_state.get("key_min_low", 3),    # 月K使用標準門檻
            price_tolerance_pct=st.session_state.get("key_tolerance", 0.5),
            timeframe="M"
        )

        # === 修改：把均線支撐壓力 + 關鍵價位(日週月)的結果也併進 gaps ===
        # 順序：缺口 → 大量K棒 → 關鍵價位 → 帶量前波高 → 均線
        gaps = d_gaps + w_gaps + m_gaps + d_hv + w_hv + m_hv + key_levels_d + key_levels_w + key_levels_m + d_prev + w_prev + m_prev + ma_sr

        # === 調試：顯示現價附近的關鍵點位數量 ===
        include_dict = {"D": inc_d, "W": inc_w, "M": inc_m, "MA": inc_ma, "KEY": inc_key}
        all_gaps_at_c1_debug = [
            g for g in gaps 
            if abs(g.edge_price - c1) / c1 * 100 <= 0.3 and
            (
                (not g.timeframe.startswith("KEY") and include_dict.get(g.timeframe, True)) or
                (g.timeframe.startswith("KEY") and include_dict.get("KEY", True))
            )
        ]
        if len(all_gaps_at_c1_debug) >= 2:
            st.info(f"🎯 現價 {c1:.2f} 附近有 **{len(all_gaps_at_c1_debug)}** 個關鍵點位匯集")

        fig = make_chart(
            daily_with_today, gaps, c1, show_zones, show_labels,
            include=include_dict,
            stock_id=stock_id, stock_name=stock_name
        )

        st.plotly_chart(fig, use_container_width=True)

        # ===============================
        # 缺口 / 大量 SR 清單 + 排序提示
        # ===============================
        df_out = pd.DataFrame([g.__dict__ for g in gaps])
        if not df_out.empty:
            # ✅ 先保留一份原始（含 Pivot High + 均線 + 關鍵價位）給專區用
            df_prev_source = df_out.copy()

            # ⬇️ 缺口清單要乾淨 → 過濾掉帶量前波高、均線、關鍵價位（它們有各自的專區）
            df_out = df_out[
                (df_out["gap_type"] != "hv_prev_high") & 
                (df_out["timeframe"] != "MA") & 
                (~df_out["timeframe"].str.startswith("KEY"))
            ].copy()

            role_rank = {"resistance": 0, "at_edge": 1, "support": 2}
            tf_rank   = {"M": 0, "W": 1, "D": 2, "MA": 3, "KEY-M": 4, "KEY-W": 5, "KEY-D": 6}
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

            # --- 新增：在「提示 / 規則說明」上方顯示 5/10/24/72 日均線資訊 ---
            def _safe_fmt(v):
                try:
                    return f"{float(v):.2f}"
                except Exception:
                    return "N/A"

            def _ma_slope_label(baseline, current_price):
                """判斷均線彎向：使用現價 current_price 相對於 baseline（基準價）比較。"""
                try:
                    if baseline is None or current_price is None:
                        return "N/A"
                    b = float(baseline)
                    cur = float(current_price)
                    if cur > b:
                        return "上彎"
                    if cur < b:
                        return "下彎"
                    return "持平"
                except Exception:
                    return "N/A"

            if stock_id and today_date:
                pass  # 均線快速摘要已移至均線支撐壓力說明下方
            # --- 新增結束 ---

            
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
            # ② 關鍵價位「專區」表格（獨立）
            # ===============================
            st.markdown("---")
            st.subheader("關鍵價位（價格聚集點 Key Price Levels）")

            # 篩選出關鍵價位相關的 Gap（包含 KEY-D, KEY-W, KEY-M）
            df_key = df_prev_source[df_prev_source["timeframe"].str.startswith("KEY")].copy()

            if df_key.empty:
                st.info("未偵測到關鍵價位（可能尚未達到最小聚集次數門檻）。")
            else:
                # 排序：價位（大→小）→ 時間框架（月→週→日）→ 角色
                tf_rank_key = {"KEY-M": 0, "KEY-W": 1, "KEY-D": 2}
                df_key["tf_rank"] = df_key["timeframe"].map(tf_rank_key)
                df_key["role_rank"] = df_key["role"].map({"resistance": 0, "at_edge": 1, "support": 2})
                df_key = df_key.sort_values(["edge_price", "tf_rank", "role_rank"], ascending=[False, True, True]).reset_index(drop=True)
                
                # 加入現價標記
                df_key.insert(0, "vs_c1", np.where(df_key["edge_price"] > c1, "▲",
                                    np.where(df_key["edge_price"] < c1, "▼", "●")))
                
                # 插入 c1 分隔列
                marker_row_key = {
                    "timeframe":"—","gap_type":"—","edge_price":c1,"role":"at_edge",
                    "ka_key":"—","kb_key":"—","gap_low":c1,"gap_high":c1,"gap_width":0.0,
                    "vs_c1":"🔶 c1","role_rank":1, "tf_rank":1
                }
                df_key = pd.concat([df_key, pd.DataFrame([marker_row_key])], ignore_index=True)
                df_key = df_key.sort_values(["edge_price", "tf_rank", "role_rank"], ascending=[False, True, True]).reset_index(drop=True)
                
                # 選擇要顯示的欄位（加入 timeframe）
                cols_order_key = ["vs_c1","timeframe","gap_type","edge_price","role","ka_key"]
                show_df_key = df_key[[c for c in cols_order_key if c in df_key.columns]].copy()
                
                # 將欄位重新命名以更清楚，並美化 timeframe 顯示
                show_df_key["timeframe"] = show_df_key["timeframe"].str.replace("KEY-", "")
                show_df_key = show_df_key.rename(columns={"ka_key": "聚集次數", "gap_type": "類型", "timeframe": "週期"})
                
                # 格式化數字欄位
                num_cols_key = [c for c in ["edge_price"] if c in show_df_key.columns]
                fmt_map_key = {c: "{:.2f}" for c in num_cols_key}
                
                # 樣式設定
                def highlight_gap_type_key(val: str) -> str:
                    v = str(val)
                    if "overlap" in v:
                        return "background-color: #fff3cd; color: #d97706; font-weight: bold;"  # 重疊（最強關鍵價位）- 金黃色
                    elif "high" in v:
                        return "background-color: #ffeaea; color: #8b0000;"  # 高點聚集（通常是壓力）
                    elif "low" in v:
                        return "background-color: #e8f5e8; color: #2d5016;"  # 低點聚集（通常是支撐）
                    return ""
                
                # 週期欄位樣式（月K最重要，用深色標示）
                def highlight_timeframe(val: str) -> str:
                    v = str(val)
                    if v == "M":
                        return "background-color: #d1fae5; font-weight: bold;"  # 月K - 深綠底
                    elif v == "W":
                        return "background-color: #fed7aa; font-weight: bold;"  # 週K - 淡橘底
                    elif v == "D":
                        return "background-color: #dbeafe;"  # 日K - 淡藍底
                    return ""
                
                # c1 高亮
                def highlight_c1_row_key(row):
                    if str(row.get("vs_c1", "")).startswith("🔶"):
                        return ["background-color: #fff3cd; font-weight: bold;"] * len(row)
                    return [""] * len(row)
                
                styled_key = (
                    show_df_key
                        .style
                        .format(fmt_map_key)
                        .apply(highlight_c1_row_key, axis=1)
                        .map(highlight_gap_type_key, subset=["類型"])
                        .map(highlight_timeframe, subset=["週期"])
                )
                
                st.dataframe(styled_key, height=300, use_container_width=True)
                
                # 關鍵價位說明
                with st.expander("📘 關鍵價位說明", expanded=False):
                    st.markdown(f"""
                    **關鍵價位規則：**
                    
                    **概念：**
                    - 同一價位多次成為高點或低點，形成價格「聚集區」
                    - 這些點位往往是市場關注的重要價格水平
                    - 支撐與壓力為一體兩面：原本的壓力站上後轉為支撐，原本的支撐跌破後轉為壓力
                    
                    **分析週期（多時間框架）：**
                    - 🟢 **M (月K)**：最重要，長期關鍵價位，權重最高
                    - 🟠 **W (週K)**：中期關鍵價位，參考價值次之
                    - 🔵 **D (日K)**：短期關鍵價位，短線操作參考
                    
                    **三種類型（自動識別）：**
                    
                    1️⃣ **高點聚集** (key_high) - 紅底標示
                       - 日K：同一價位至少 {st.session_state.get("key_min_high_d", 4)} 次成為「高點」
                       - 週/月K：同一價位至少 {st.session_state.get("key_min_high", 3)} 次成為「高點」
                       - 代表市場反覆測試的壓力位
                       - 顯示：`X次高`
                    
                    2️⃣ **低點聚集** (key_low) - 綠底標示
                       - 日K：同一價位至少 {st.session_state.get("key_min_low_d", 4)} 次成為「低點」
                       - 週/月K：同一價位至少 {st.session_state.get("key_min_low", 3)} 次成為「低點」
                       - 代表市場反覆測試的支撐位
                       - 顯示：`X次低`
                    
                    3️⃣ **高低點重疊** (key_overlap) - 🌟金黃色粗體標示🌟
                       - 同一價位既是高點聚集又是低點聚集
                       - **最強關鍵價位**（箱型區間的關鍵價）
                       - 顯示：`X次高+Y次低`
                       - 突破或跌破此價位往往引發大行情！
                    
                    **實例說明：**
                    ```
                    範例 A：100元在日K出現4次高點 → key_high_D (短期壓力)
                    範例 B：95元在週K出現3次低點 → key_low_W (中期支撐)
                    範例 C：98元在月K出現3次高點 + 3次低點
                            → key_overlap_M (3次高+3次低) ⭐最強⭐
                            → 98元是長期箱型區間的關鍵價，突破看漲/跌破看跌
                    ```
                    
                    **為什麼連續測試也要計入？**
                    - 連續多日在同一價位受阻 → **更強的壓力證據**
                    - 連續多日在同一價位獲得支撐 → **更強的支撐證據**
                    - 例如：連續 3 天高點都是 100，代表市場反覆確認 100 是重要壓力
                    - 市場「反覆測試」同一價位本身就是該價位重要性的體現
                    
                    **判斷標準（當前設定）：**
                    - 日K高點聚集門檻：**{st.session_state.get("key_min_high_d", 4)}** 次（較嚴格，減少雜訊）
                    - 日K低點聚集門檻：**{st.session_state.get("key_min_low_d", 4)}** 次（較嚴格，減少雜訊）
                    - 週/月K高點門檻：**{st.session_state.get("key_min_high", 3)}** 次（標準）
                    - 週/月K低點門檻：**{st.session_state.get("key_min_low", 3)}** 次（標準）
                    - 價格容差範圍：**±{st.session_state.get("key_tolerance", 0.5)}%**
                    - 分析週期：**日K、週K、月K** (同時掃描三種時間框架)
                    
                    **圖表顯示：**
                    - 線寬：**月K(3.2) > 週K(2.8) > 日K(2.5)** (長週期更粗)
                    - 顏色：金黃色區域標記（不透明度：月K 90% > 週K 70% > 日K 50%）
                    - 使用單一「KEY 關鍵價位」勾選框控制顯示
                    
                    **實務應用：**
                    - 高點聚集：多次測試未突破 → 強壓力
                    - 低點聚集：多次測試未跌破 → 強支撐
                    - **🌟高低點重疊🌟**：
                      * 最強關鍵價位（箱型區間）
                      * 向上突破 → 強烈看漲信號
                      * 向下跌破 → 強烈看跌信號
                      * 在此價位附近震盪 → 區間操作
                    - 現價在關鍵價位上方：原壓力轉為支撐
                    - 現價在關鍵價位下方：原支撐轉為壓力
                    - **月K關鍵價位 > 週K > 日K**（長週期權重更高）
                    
                    **聚集次數的意義：**
                    - 3次聚集：基本關鍵價位
                    - 5次以上：非常重要的價格水平
                    - 高低點各5次以上重疊：極度重要的箱型關鍵價
                    - **月K級別的5次以上重疊：終極關鍵價位**
                    """)

            # ===============================
            # ③ 帶量前波高「專區」表格（獨立）
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

                # 規則說明
                with st.expander("📖 「帶量前波高 Pivot High」規則說明", expanded=False):
                    st.markdown("""
                    ### 🎯 核心概念
                    當股價**帶大量**突破或回測時，找出**最近的前波高點**作為關鍵壓力/支撐參考。
                    
                    ---
                    
                    ### 📋 判斷條件
                    
                    #### 1️⃣ **帶大量定義**（兩條件任一成立）
                    - **條件 A（均量倍數）**：
                      - 成交量 ≥ 近 20 均量 × 1.7
                      - 且 成交量 ≥ 前一根量 × 0.8（避免量縮）
                    - **條件 B（相對前根倍數）**：
                      - 成交量 ≥ 前一根量 × 1.2
                    
                    #### 2️⃣ **Pivot High（樞紐高點）定義**
                    - 該 K 棒的 **high** 是左右 N 根中的**唯一最高點**
                    - 參數設定：
                      - 日K：左 3 右 3（共 7 根中的最高）
                      - 週K：左 2 右 2（共 5 根中的最高）
                      - 月K：左 1 右 1（共 3 根中的最高）
                    - ⚠️ **同高並列不算**（避免模糊訊號）
                    
                    #### 3️⃣ **觸發機制**
                    - 當某根 K 棒**帶大量**時（觸發棒 `trigger_key`）
                    - 向左回看最近的 **Pivot High**（`pivot_key`）
                    - 且該 Pivot High **本身也必須帶大量**
                    - 將該 Pivot High 的價位標記為關鍵壓力/支撐
                    
                    ---
                    
                    ### 🔄 動態角色轉換
                    - **現價上方** → 壓力 (resistance) ▲
                    - **現價下方** → 支撐 (support) ▼
                    - **現價相同** → 交界 (at_edge) ●
                    
                    ---
                    
                    ### 📊 排序邏輯（由上到下）
                    1. **時間框架**：月K → 週K → 日K
                    2. **發生時間**：越近期越前面（`pivot_key` 降序）
                    3. **角色**：壓力 → 交界 → 支撐
                    4. **價位**：高價位 → 低價位
                    
                    ---
                    
                    ### 💡 實戰應用
                    - **壓力位策略**：
                      - 現價接近 Pivot High 壓力 → 觀察是否「價到量縮」（可能假突破）
                      - 帶量突破壓力 → 確認突破有效，後續回測壓力轉支撐
                    
                    - **支撐位策略**：
                      - 現價回測 Pivot High 支撐 → 觀察是否「價跌量縮」（支撐有效）
                      - 跌破支撐且帶大量 → 支撐失效，注意後續下跌風險
                    
                    - **強度判斷**：
                      - **月K > 週K > 日K**（時間框架越大越重要）
                      - **越近期的 Pivot High 越有參考價值**
                    
                    ---
                    
                    ### 📌 欄位說明
                    - **vs_c1**：與現價關係（▲壓力 / ▼支撐 / ●交界）
                    - **timeframe**：時間框架（D=日K / W=週K / M=月K）
                    - **edge_price**：Pivot High 的價位
                    - **pivot_key**：Pivot High 發生的時間
                    - **trigger_key**：觸發偵測的帶量 K 棒時間
                    - 🔶 **c1 標記列**：現價參考線（黃底顯示）
                    """)

            # ===============================
            # ④ 均線支撐壓力「專區」表格（獨立）
            # ===============================
            st.markdown("---")
            st.subheader("均線支撐壓力（MA S/R）")

            # 篩選出均線相關的 Gap
            df_ma = df_prev_source[df_prev_source["timeframe"] == "MA"].copy()

            if df_ma.empty:
                st.info("未偵測到均線支撐壓力。")
            else:
                # 排序：角色 → 價位 → gap_type
                df_ma["role_rank"] = df_ma["role"].map({"resistance": 0, "at_edge": 1, "support": 2})
                df_ma = df_ma.sort_values(["role_rank", "edge_price"], ascending=[True, False]).reset_index(drop=True)
                
                # 加入現價標記
                df_ma.insert(0, "vs_c1", np.where(df_ma["edge_price"] > c1, "▲",
                                    np.where(df_ma["edge_price"] < c1, "▼", "●")))
                
                # 插入 c1 分隔列
                marker_row_ma = {
                    "timeframe":"—","gap_type":"—","edge_price":c1,"role":"at_edge",
                    "ka_key":"—","kb_key":"—","gap_low":c1,"gap_high":c1,"gap_width":0.0,
                    "vs_c1":"🔶 c1","role_rank":1
                }
                df_ma = pd.concat([df_ma, pd.DataFrame([marker_row_ma])], ignore_index=True)
                df_ma = df_ma.sort_values(["role_rank","edge_price"], ascending=[True,False]).reset_index(drop=True)
                
                # 選擇要顯示的欄位
                cols_order_ma = ["vs_c1","gap_type","edge_price","role","ka_key","kb_key"]
                show_df_ma = df_ma[[c for c in cols_order_ma if c in df_ma.columns]].copy()
                
                # 格式化數字欄位
                num_cols_ma = [c for c in ["edge_price"] if c in show_df_ma.columns]
                fmt_map_ma = {c: "{:.2f}" for c in num_cols_ma}
                
                # 樣式設定
                def highlight_gap_type_ma(val: str) -> str:
                    v = str(val)
                    if "up" in v or "baseline" in v or "deduction" in v:
                        return "background-color: #e8f5e8; color: #2d5016;"
                    elif "down" in v:
                        return "background-color: #ffeaea; color: #8b0000;"
                    return ""
                
                # c1 高亮
                def highlight_c1_row_ma(row):
                    if str(row.get("vs_c1", "")).startswith("🔶"):
                        return ["background-color: #fff3cd; font-weight: bold;"] * len(row)
                    return [""] * len(row)
                
                styled_ma = (
                    show_df_ma
                        .style
                        .format(fmt_map_ma)
                        .apply(highlight_c1_row_ma, axis=1)
                        .map(highlight_gap_type_ma, subset=["gap_type"])
                )
                
                st.dataframe(styled_ma, height=300, use_container_width=True)
                
                # 均線支撐壓力說明
                with st.expander("📘 均線支撐壓力說明", expanded=False):
                    st.markdown("""
                    **均線支撐壓力規則：**
                    
                    **1. 上彎/下彎均線：**
                    - 上彎且在現價下方的均線 → 支撐
                    - 下彎且在現價上方的均線 → 壓力
                    - 判斷依據：現價 vs 基準價（現價 > 基準價 = 上彎；現價 < 基準價 = 下彎）
                    
                    **2. 基準價與扣抵值：**
                    - 找出距離現價最近的均線（5/10/24/72日均）
                    - 該均線的基準價：在現價上方為壓力，在現價下方為支撐
                    - 該均線的扣抵值：在現價上方為壓力，在現價下方為支撐
                    
                    **強度說明：**
                    - 基準價、扣抵值：一級加粗（primary）
                    - 上彎/下彎均線：二級一般（secondary）
                    """)

                # 均線快速摘要區塊（折疊）
                if stock_id and today_date:
                    with st.expander("📊 均線快速摘要（5 / 10 / 24 / 72）", expanded=False):
                        for n in (5, 10, 24, 72):
                            ma = None
                            try:
                                ma = compute_ma_with_today(stock_id, today_date, c1, n)
                            except Exception:
                                ma = None

                            baseline = deduction = None
                            try:
                                baseline, deduction, *_ = get_baseline_and_deduction(stock_id, today_date, n=n)
                            except Exception:
                                baseline = deduction = None

                            st.markdown(
                                f"- {n}日均：點位 {_safe_fmt(ma)} ／ {_ma_slope_label(baseline, c1)} ／ 基準價 {_safe_fmt(baseline)} ／ 扣抵值 {_safe_fmt(deduction)}",
                                unsafe_allow_html=True,
                            )


        else:
            st.info("此範圍內未偵測到缺口或大量 K 棒 S/R。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
