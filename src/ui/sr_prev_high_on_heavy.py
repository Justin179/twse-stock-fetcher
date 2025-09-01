# -*- coding: utf-8 -*-
"""
帶大量的「前波高點」→ 壓力（D/W/M 都可用）
------------------------------------------------
核心條件：
  1) 目標 K 棒為『帶大量』(is_heavy == True)
  2) 從該棒向左回看，找到最近的一根『pivot high』（唯一最高的樞紐高點）
  3) 該 pivot high K 棒本身也必須是『帶大量』（pivot_heavy_only=True）
  4) 以該 pivot high 的 high 當作『前波高』價位 → 壓力候選（最後仍會依 c1 動態轉換）

整合方式（在你的主程式）：
    from sr_prev_high_on_heavy import scan_prev_high_on_heavy_from_df, scan_prev_high_on_heavy_all

    d_prev = scan_prev_high_on_heavy_from_df(
        daily_with_today.rename(columns={"date": "key"}),
        key_col="key", timeframe="D", c1=c1,
        window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio,
        pivot_left=3, pivot_right=3, max_lookback=120, pivot_heavy_only=True
    )
    w_prev = scan_prev_high_on_heavy_from_df(
        wk, key_col="key", timeframe="W", c1=c1,
        window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio,
        pivot_left=2, pivot_right=2, max_lookback=60, pivot_heavy_only=True
    )
    m_prev = scan_prev_high_on_heavy_from_df(
        mo, key_col="key", timeframe="M", c1=c1,
        window=20, multiple=hv_ma_mult, prev_multiple=hv_prev_mult, no_shrink_ratio=no_shrink_ratio,
        pivot_left=1, pivot_right=1, max_lookback=36, pivot_heavy_only=True
    )

    gaps = gaps + d_prev + w_prev + m_prev
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

import pandas as pd
import numpy as np


# ---- 與你現有的結構對齊（型別提示用；主程式已有同名 Dataclass 亦可直接共用） ----
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
    strength: str = "secondary"


# ================ 帶大量判定（等同你現用規則，可調參數） ================
def enrich_kbar_signals(df: pd.DataFrame,
                        ma_window: int = 20,
                        heavy_ma_multiple: float = 1.7,
                        heavy_prev_multiple: float = 1.2,
                        no_shrink_ratio: float = 0.8) -> pd.DataFrame:
    d = df.copy()
    d["v_maN"] = d["volume"].rolling(window=ma_window, min_periods=ma_window).mean()
    d["prev_volume"] = d["volume"].shift(1)

    cond_ma = (d["v_maN"].notna()) & (d["volume"] >= heavy_ma_multiple * d["v_maN"])
    cond_no_shrink = d["prev_volume"].notna() & (d["volume"] >= no_shrink_ratio * d["prev_volume"])
    d["is_heavy_ma"] = cond_ma & cond_no_shrink

    d["is_heavy_prev"] = d["prev_volume"].notna() & (d["volume"] >= heavy_prev_multiple * d["prev_volume"])
    d["is_heavy"] = d["is_heavy_ma"] | d["is_heavy_prev"]

    d["prev_close"] = d["close"].shift(1)
    d["up_vs_prev"] = d["prev_close"].notna() & (d["close"] > d["prev_close"])
    d["down_vs_prev"] = d["prev_close"].notna() & (d["close"] < d["prev_close"])
    d["up_today"] = d["close"] > d["open"]
    d["down_today"] = d["close"] < d["open"]

    d["is_true_red"] = d["up_vs_prev"] & d["up_today"]
    d["is_true_green"] = d["down_vs_prev"] & d["down_today"]
    return d


# ================== Pivot High（唯一最高，避免同高並列） ==================
def find_pivot_high_indices(high_series: pd.Series, left: int = 3, right: int = 3) -> List[int]:
    hs = high_series.values
    n = len(hs)
    pivots: List[int] = []
    for i in range(n):
        l = max(0, i - left)
        r = min(n, i + right + 1)
        seg = hs[l:r]
        if seg.size == 0:
            continue
        hmax = seg.max()
        # 唯一最高（同高並列不算）
        if hs[i] == hmax and (seg > hs[i]).sum() == 0 and (seg == hs[i]).sum() >= 1:
            pivots.append(i)
    return pivots


def _fmt_key_for_tf(val, timeframe: str) -> str:
    if timeframe == "D":
        try:
            return pd.to_datetime(val).strftime("%Y-%m-%d")
        except Exception:
            s = str(val)
            return s[:10] if len(s) >= 10 else s
    return str(val)


# ================== 主功能：帶大量「前波高」→ 壓力 ==================
def scan_prev_high_on_heavy_from_df(df: pd.DataFrame, *,
                                    key_col: str,
                                    timeframe: str,
                                    c1: float,
                                    # heavy 參數
                                    window: int = 20,
                                    multiple: float = 1.7,
                                    prev_multiple: float = 1.2,
                                    no_shrink_ratio: float = 0.8,
                                    # pivot 參數
                                    pivot_left: int = 3,
                                    pivot_right: int = 3,
                                    max_lookback: Optional[int] = 120,
                                    # 嚴格條件：pivot 本身也要帶大量
                                    pivot_heavy_only: bool = True,
                                    # 去重
                                    dedup_eps: float = 0.01,
                                    dedup_keep: str = "last"  # "first" 或 "last"
                                    ) -> List[Gap]:
    """
    回傳與你現用 Gap 相容的清單；gap_type = "hv_prev_high"。
    強度：pivot 是 heavy → primary，否則 secondary。
    """
    out: List[Gap] = []
    if df is None or df.empty:
        return out

    d = enrich_kbar_signals(
        df,
        ma_window=window,
        heavy_ma_multiple=multiple,
        heavy_prev_multiple=prev_multiple,
        no_shrink_ratio=no_shrink_ratio,
    ).reset_index(drop=True)

    # 先找全體 pivot high，再視需要過濾「pivot 必須 heavy」
    pivot_idx_all = find_pivot_high_indices(d["high"], left=int(pivot_left), right=int(pivot_right))
    if not pivot_idx_all:
        return out

    if pivot_heavy_only:
        pivot_set = {i for i in pivot_idx_all if bool(d.at[i, "is_heavy"])}
    else:
        pivot_set = set(pivot_idx_all)

    if not pivot_set:
        return out

    # 只檢視『帶大量』的目標 K 棒（右側觸發棒）
    heavy_idx = list(np.where(d["is_heavy"].values)[0])
    if not heavy_idx:
        return out

    # 暫存 edge 價位以做去重（同價位 ± eps 視為同一群）
    cand_map: Dict[float, List[Tuple[int, int]]] = {}

    for h in heavy_idx:
        left_bound = 0 if max_lookback is None else max(0, h - int(max_lookback))
        # 前波（只看左側）且必須是允許的 pivot（若 pivot_heavy_only=True，這裡必為 heavy）
        candidates = [i for i in pivot_set if (left_bound <= i < h)]
        if not candidates:
            continue
        p = max(candidates)  # 最近的那一根
        price = float(round(d.at[p, "high"], 3))
        cand_map.setdefault(price, []).append((p, h))

    if not cand_map:
        return out

    # 去重：把 close 價位相近的群組起來
    prices_sorted = sorted(cand_map.keys())
    groups: List[List[float]] = []
    for pr in prices_sorted:
        if not groups or abs(pr - groups[-1][-1]) > float(dedup_eps):
            groups.append([pr])
        else:
            groups[-1].append(pr)

    for grp in groups:
        rep_price = grp[-1] if dedup_keep == "last" else grp[0]
        pairs = []
        for pr in grp:
            pairs.extend(cand_map.get(pr, []))
        if not pairs:
            continue

        p_idx, h_idx = (pairs[-1] if dedup_keep == "last" else pairs[0])

        ka_key = _fmt_key_for_tf(d.at[p_idx, key_col], timeframe)  # pivot 的 key
        kb_key = _fmt_key_for_tf(d.at[h_idx, key_col], timeframe)  # heavy 觸發棒的 key

        role = "support" if c1 > rep_price else "resistance" if c1 < rep_price else "at_edge"
        strength = "primary" if bool(d.at[p_idx, "is_heavy"]) else "secondary"

        out.append(Gap(
            timeframe=timeframe,
            gap_type="hv_prev_high",
            edge_price=float(round(rep_price, 3)),
            role=role,
            ka_key=ka_key,
            kb_key=kb_key,
            gap_low=float(round(rep_price, 3)),
            gap_high=float(round(rep_price, 3)),
            gap_width=0.0,
            strength=strength
        ))

    return out


# 便利函式：一次算 D/W/M（你也可分開呼叫以便用不同 pivot_left/right）
def scan_prev_high_on_heavy_all(
    daily_with_today: pd.DataFrame, wk: pd.DataFrame, mo: pd.DataFrame, *,
    c1: float, hv_params: Optional[dict] = None,
    d_pivot=(3, 3), w_pivot=(2, 2), m_pivot=(1, 1),
    d_lookback=120, w_lookback=60, m_lookback=36,
    pivot_heavy_only: bool = True
) -> List[Gap]:
    hvp = dict(window=20, multiple=1.7, prev_multiple=1.2, no_shrink_ratio=0.8)
    if hv_params:
        hvp.update(hv_params)

    out: List[Gap] = []
    if daily_with_today is not None and not daily_with_today.empty:
        out += scan_prev_high_on_heavy_from_df(
            daily_with_today.rename(columns={"date": "key"}),
            key_col="key", timeframe="D", c1=c1,
            pivot_left=int(d_pivot[0]), pivot_right=int(d_pivot[1]),
            max_lookback=int(d_lookback), pivot_heavy_only=pivot_heavy_only, **hvp
        )
    if wk is not None and not wk.empty:
        out += scan_prev_high_on_heavy_from_df(
            wk, key_col="key", timeframe="W", c1=c1,
            pivot_left=int(w_pivot[0]), pivot_right=int(w_pivot[1]),
            max_lookback=int(w_lookback), pivot_heavy_only=pivot_heavy_only, **hvp
        )
    if mo is not None and not mo.empty:
        out += scan_prev_high_on_heavy_from_df(
            mo, key_col="key", timeframe="M", c1=c1,
            pivot_left=int(m_pivot[0]), pivot_right=int(m_pivot[1]),
            max_lookback=int(m_lookback), pivot_heavy_only=pivot_heavy_only, **hvp
        )
    return out
