def score_attack_stocks(filtered_stocks: list[str], prices_cache: dict[str, dict]) -> list[dict]:
    """
    個股評分模組：利用已快取的即時價格與量能資料，對通過二篩的個股進行量化評分與排序。
    不重複呼叫富邦 API，確保效能。
    
    評分維度示例 (總分 100 分)：
    1. 今日漲幅 (40%): 漲幅 >= 7% 得滿分，依比例遞減；跌則得 0 分。
    2. 收盤強勢度 (30%): 位於今日高低點區間的位置高低 (c1 - l) / (h - l)，越高越強。
    3. 量能配合度 (30%): 若有成交量資料，可評估交易是否熱絡或與昨日成交量做比較（暫定基本分/基礎量能評分）。
    
    回傳：
        已排序的評分結果列表，格式如：
        [
            {"stock_id": "2330", "score": 85.5, "change_pct": 2.5, ...},
            ...
        ]
    """
    scored_results = []
    
    print(f"\n💯 啟動「個股評分模組」，開始評估 {len(filtered_stocks)} 檔個股...")
    
    for stock_id in filtered_stocks:
        price_info = prices_cache.get(stock_id)
        if not price_info:
            print(f"⚠️ 找不到 {stock_id} 的即時價格快取，無法進行評分。")
            continue
        
        # 變數c1,c2,h,l,v確實都是透過 API 取得的當日即時數據（或是 API 維護時的資料庫備援）。
        c1 = price_info.get("c1")  # 現價
        c2 = price_info.get("c2")  # 昨收
        h = price_info.get("h")    # 今日最高
        l = price_info.get("l")    # 今日最低
        v = price_info.get("v", 0) # 成交量
        
        if c1 is None or c2 is None or c2 == 0:
            continue
            
        # 1. 今日漲幅評分 (最大分數 40 分)
        change_pct = ((c1 - c2) / c2) * 100
        # 漲幅大於等於 7% 給滿分 40，其餘按比例 (change_pct / 7) * 40
        if change_pct >= 7:
            漲幅_score = 40.0
        elif change_pct > 0:
            漲幅_score = (change_pct / 7.0) * 40.0
        else:
            漲幅_score = 0.0
            
        # 2. 今日收盤強勢度評分 (最大分數 30 分)
        # 用現價在今日高低點的相對位置：(c1 - l) / (h - l)
        strong_pos_score = 0.0
        if h is not None and l is not None and h > l:
            relative_pos = (c1 - l) / (h - l) # 0.0 ~ 1.0
            strong_pos_score = relative_pos * 30.0
        else:
            # 若無高低點或平盤，給基礎分數 15 分
            strong_pos_score = 15.0
            
        # 3. 量能配合度評分 (最大分數 30 分)
        # 成交量若大於 1000 張代表具備足夠流動性，可給 20-30 分，其餘依比例
        vol_score = 15.0
        if v is not None:
            if v >= 1000:
                vol_score = 30.0
            elif v > 0:
                vol_score = 15.0 + (v / 1000.0) * 15.0

        total_score = round(漲幅_score + strong_pos_score + vol_score, 2)
        
        scored_results.append({
            "stock_id": stock_id,
            "score": total_score,
            "change_pct": round(change_pct, 2),
            "close_price": c1,
            "volume": v
        })
        
    # 依評分由高到低進行排序
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    
    return scored_results
