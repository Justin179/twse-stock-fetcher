#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享股票選擇器
用於在多個 Streamlit 應用之間同步當前選擇的股票
"""
import os
from pathlib import Path
from typing import Optional

# 共享檔案路徑
SHARED_STOCK_FILE = Path(__file__).resolve().parents[2] / "data" / "current_selected_stock.txt"


def save_selected_stock(stock_id: str) -> None:
    """
    儲存當前選擇的股票代碼到共享檔案
    
    Args:
        stock_id: 股票代碼（例如 "2330"）
    """
    try:
        SHARED_STOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SHARED_STOCK_FILE, "w", encoding="utf-8") as f:
            f.write(stock_id.strip())
    except Exception as e:
        print(f"⚠️ 無法儲存選擇的股票：{e}")


def load_selected_stock() -> Optional[str]:
    """
    從共享檔案讀取當前選擇的股票代碼
    
    Returns:
        股票代碼，若檔案不存在或讀取失敗則回傳 None
    """
    try:
        if not SHARED_STOCK_FILE.exists():
            return None
        with open(SHARED_STOCK_FILE, "r", encoding="utf-8") as f:
            stock_id = f.read().strip()
            return stock_id if stock_id else None
    except Exception as e:
        print(f"⚠️ 無法讀取選擇的股票：{e}")
        return None


def get_last_selected_or_default(default: str = "2330") -> str:
    """
    取得上次選擇的股票代碼，若無則回傳預設值
    
    Args:
        default: 預設股票代碼
        
    Returns:
        股票代碼
    """
    stock_id = load_selected_stock()
    return stock_id if stock_id else default
