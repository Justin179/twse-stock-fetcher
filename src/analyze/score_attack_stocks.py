from ui.volume_forecast import forecast_by_avg_rate

def score_attack_stocks(filtered_stocks: list[str], prices_cache: dict[str, dict]) -> list[dict]:
    """
    個股當日強勢程度評分模組：利用已快取的即時價格與量能資料，對通過二篩的個股進行量化評分與排序。
    不重複呼叫富邦 API，確保效能。
    
    評分維度 (總分 100 分)：
    1. 漲幅與量能配合度 (80%): 
       - 價格基分 (0-40): 漲幅 >= 7% 得 40 分，其餘按比例。
       - 量能基分 (0/15): 預估收盤量 >= 昨量 80% 時給 15 分。
       - 強勢加成 (x1.5): 若實時量 > 昨量 或 預估量 > 昨量，總和乘以 1.5 (最高 80 分)。
    2. 收盤強勢度 (20%): 位於今日高低點區間的位置高低 (c1 - l) / (h - l)，越高越強。
    
    回傳：
        已排序的評分結果列表
    """
    scored_results = []
    
    print(f"\n💯 啟動「個股評分模組」，開始評估 {len(filtered_stocks)} 檔個股...")
    
    for stock_id in filtered_stocks:
        price_info = prices_cache.get(stock_id)
        if not price_info:
            print(f"⚠️ 找不到 {stock_id} 的即時價格快取，無法進行評分。")
            continue
        
        # 變數c1,c2,h,l,v確實都是透過 API 取得的當日即時數據（或是 API 維護時的資料庫備援）。
        c1 = price_info.get("c1")    # 現價
        c2 = price_info.get("c2")    # 昨收
        h = price_info.get("h")      # 今日最高
        l = price_info.get("l")      # 今日最低
        v = price_info.get("v", 0)   # 當前成交量 (張)
        y_v = price_info.get("y_v", 0) # 昨成交量 (張)
        
        if c1 is None or c2 is None or c2 == 0:
            continue
            
        # --- 1. & 3. 整合：今日漲幅與量能配合度 (最大分數 80 分) ---
        # A. 價格基分 (max 40)
        change_pct = ((c1 - c2) / c2) * 100
        if change_pct >= 7:
            price_base = 40.0
        elif change_pct > 0:
            price_base = (change_pct / 7.0) * 40.0
        else:
            price_base = 0.0
        
        # B. 量能基分與加成
        vol_base = 0.0
        vol_multiplier = 1.0
        
        if y_v > 0:
            # 計算預估量 (使用 project 模組)
            f_res = forecast_by_avg_rate(v, y_v)
            proj_v = f_res.get("forecast_volume", 0) if f_res else v
            
            # 若預估量達到昨量的 80%，給予基分
            if proj_v >= (y_v * 0.8):
                vol_base = 15.0
            
            # 若已經量增 (實時 > 昨) 或 預估量增 (預估 > 昨)，視為強勢追價
            if v >= y_v or proj_v >= y_v:
                vol_multiplier = 1.5
        else:
            # 無昨量資料時，給予基礎分
            vol_base = 10.0

        price_volume_score = min(80.0, (price_base + vol_base) * vol_multiplier)

        # --- 2. 今日收盤強勢度評分 (最大分數 20 分) ---
        # 用現價在今日高低點的相對位置：(c1 - l) / (h - l)
        strong_pos_score = 0.0
        if h is not None and l is not None and h > l:
            relative_pos = (c1 - l) / (h - l) # 0.0 ~ 1.0
            strong_pos_score = relative_pos * 20.0
        else:
            # 若無高低點或平盤，給基礎分數 10 分
            strong_pos_score = 10.0
            
        total_score = round(price_volume_score + strong_pos_score, 2)
        
        scored_results.append({
            "stock_id": stock_id,
            "score": total_score,
            "change_pct": round(change_pct, 2),
            "close_price": c1,
            "volume": v,
            "y_volume": round(y_v, 1) if y_v else 0
        })
        
    # 依評分由高到低進行排序
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    
    return scored_results
