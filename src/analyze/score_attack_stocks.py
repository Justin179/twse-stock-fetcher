from ui.volume_forecast import forecast_by_avg_rate
import sqlite3
import pandas as pd
from ui.price_break_display_module import (
    get_volume_status,
    get_baseline_and_deduction, compute_recent_netbuy_streaks,
    compute_institutional_netbuy_days,
    is_uptrending_now, compute_ma_with_today
)
from analyze.analyze_price_break_conditions_dataloader import (
    get_week_month_high_low, get_recent_hl_before_date
)
from analyze.moving_average_weekly import is_price_above_upward_wma5

def score_attack_stocks(filtered_stocks: list[str], prices_cache: dict[str, dict]) -> list[dict]:
    """
    個股當日強勢程度評分模組：利用已快取的即時價格與量能資料，對通過二篩的個股進行量化評分與排序。
    整合價格、量能、技術指標、與籌碼連買等多維度加分項。
    
    評分維度：
    1. 基礎得分 (漲幅+量能 80%, 收盤強勢 20%)
    2. 額外訊號加分 (直接累加於總分)
    """
    scored_results = []
    db_path = "data/institution.db"
    
    print(f"\n💯 啟動「個股當日強勢程度評分」，開始評估 {len(filtered_stocks)} 檔個股...")
    
    for stock_id in filtered_stocks:
        price_info = prices_cache.get(stock_id)
        if not price_info:
            continue
        
        c1 = price_info.get("c1")
        c2 = price_info.get("c2")
        h = price_info.get("h")
        l = price_info.get("l")
        v = price_info.get("v", 0)
        y_v = price_info.get("y_v", 0)
        today_date = price_info.get("date")
        
        if c1 is None or c2 is None or c2 == 0:
            continue
            
        # --- (A) 基礎評分 (100分制) ---
        change_pct = ((c1 - c2) / c2) * 100
        price_base = (change_pct / 7.0) * 40.0 if 0 < change_pct < 7 else (40.0 if change_pct >= 7 else 0.0)
        
        # 量能基分與加成
        vol_base = 0.0
        vol_multiplier = 1.0
        if y_v > 0:
            f_res = forecast_by_avg_rate(v, y_v)
            proj_v = f_res.get("forecast_volume", 0) if f_res else v
            if proj_v >= (y_v * 0.8): vol_base = 15.0
            if v >= y_v or proj_v >= y_v: vol_multiplier = 1.5
        else:
            vol_base = 10.0

        price_volume_score = min(80.0, (price_base + vol_base) * vol_multiplier)

        # 收盤強勢度 (20分)
        strong_pos_score = 10.0
        if h is not None and l is not None and h > l:
            strong_pos_score = ((c1 - l) / (h - l)) * 20.0
        
        base_total = price_volume_score + strong_pos_score
        
        # --- (B) 額外強勢訊號加分 ---
        extra_bonus = 0.0
        try:
            # 獲取基準與扣抵
            b, d, d1, d2, d3, pb = get_baseline_and_deduction(stock_id, today_date)
            vol_status = get_volume_status(price_info, y_v * 1000.0 if y_v else 0, stock_id)
            price_status = "漲" if c1 > c2 else ("跌" if c1 < c2 else "平")
            
            # ✅ 今天強勢: 今壓上升 + 價漲量增
            if b and pb and b > pb and price_status == "漲" and vol_status == "量增":
                extra_bonus += 5.0
            
            # ✅ 強勢股: 扣抵向上 + 價漲量增
            if d and b and d > b and price_status == "漲" and vol_status == "量增":
                extra_bonus += 5.0

            # --- 趨勢加分 (向上趨勢盤，帶量 破壓追價!) ---
            w1, w2, m1, m2 = get_week_month_high_low(stock_id)
            ma5 = compute_ma_with_today(stock_id, today_date, c1, 5)
            ma10 = compute_ma_with_today(stock_id, today_date, c1, 10)
            ma24 = compute_ma_with_today(stock_id, today_date, c1, 24)
            above_upward_wma5 = is_price_above_upward_wma5(stock_id, today_date, c1, debug_print=False)

            if is_uptrending_now(stock_id, today_date, c1, w1, m1, ma5, ma10, ma24, above_upward_wma5):
                # 趨勢向上基本分 +5，若帶量則加成至 +10
                if vol_status == "量增":
                    extra_bonus += 10.0
                else:
                    extra_bonus += 5.0

            # --- 三盤突破與過昨高 (階梯加分) ---
            three_bar_bonus = 0.0
            prev_hl = get_recent_hl_before_date(stock_id, today_date, limit=2)
            if not prev_hl.empty and len(prev_hl) >= 2:
                y_high = float(prev_hl.iloc[0]["high"])
                p_high = float(prev_hl.iloc[1]["high"])
                if c1 > y_high:
                    three_bar_bonus = 2.0 # 過昨高
                    if c1 > p_high:
                        three_bar_bonus = 5.0 # 三盤突破
                        if vol_status == "量增":
                            three_bar_bonus = 8.0 # 三盤帶量突破
            extra_bonus += three_bar_bonus
        except Exception:
            pass

        # --- (C) 籌碼面加分 (主力/外資/投信) ---
        try:
            m_s, f_s, t_s = compute_recent_netbuy_streaks(stock_id, db_path)
            for streak in [m_s, f_s, t_s]:
                if streak >= 3:
                    extra_bonus += min(5.0, (streak - 2))

            m_d, f_d, t_d = compute_institutional_netbuy_days(stock_id, 10, db_path)
            for days in [m_d, f_d, t_d]:
                if days >= 6:
                    extra_bonus += min(5.0, (days - 5))
        except Exception:
            pass

        final_score = round(min(100.0, base_total + extra_bonus), 2)
        
        scored_results.append({
            "stock_id": stock_id,
            "score": final_score,
            "change_pct": round(change_pct, 2),
            "close_price": c1,
            "volume": v,
            "y_volume": round(y_v, 1)
        })
        
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results
