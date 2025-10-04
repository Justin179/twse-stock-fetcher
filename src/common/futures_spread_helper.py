import os
import json
import sqlite3
import subprocess
from datetime import datetime, date
from typing import Optional, Dict, Any

def get_latest_trade_date_from_db() -> Optional[str]:
    """從 twse_prices 資料庫獲取最新交易日期"""
    try:
        conn = sqlite3.connect("data/institution.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(date) FROM twse_prices")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else None
    except Exception:
        return None

def load_futures_spread_cache() -> Optional[Dict[str, Any]]:
    """讀取期現價差快取檔案"""
    cache_file = "data/futures_spread_cache.json"
    if not os.path.exists(cache_file):
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def save_futures_spread_cache(data: Dict[str, Any]) -> None:
    """保存期現價差到快取檔案"""
    cache_file = "data/futures_spread_cache.json"
    os.makedirs("data", exist_ok=True)
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存期現價差快取失敗: {e}")

def fetch_futures_spread_data() -> Optional[Dict[str, Any]]:
    """執行期現價差程式獲取最新資料"""
    try:
        import sys
        script_path = os.path.join("src", "futures_spread", "get_tw_fut_spread.py")
        
        # 使用當前 Python 解釋器的完整路徑
        python_path = sys.executable
        
        result = subprocess.run([
            python_path, script_path, "--json"
        ], capture_output=True, text=True, encoding='utf-8', cwd=os.getcwd())
        
        # print(f"使用 Python: {python_path}")
        # print(f"工作目錄: {os.getcwd()}")
        # print(f"執行結果: {result.returncode}")
        # print(f"stdout: {result.stdout}")
        # print(f"stderr: {result.stderr}")
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return None
    except Exception as e:
        print(f"執行期現價差程式出錯: {e}")
        return None


def get_futures_spread_info() -> Optional[Dict[str, Any]]:
    """
    獲取期現價差資訊（智慧快取）
    先檢查快取，如果資料不是最新交易日的就重新獲取
    """
    # 確保 data 目錄存在
    os.makedirs("data", exist_ok=True)
    
    latest_trade_date = get_latest_trade_date_from_db()
    if not latest_trade_date:
        # 如果無法獲取最新交易日，直接獲取新資料
        data = fetch_futures_spread_data()
        if data:
            save_futures_spread_cache(data)
        return data
    
    # 檢查快取
    cached_data = load_futures_spread_cache()

    # 👇 這裡比對日期：檢查快取資料的交易日是否等於最新交易日
    if cached_data and cached_data.get("trade_date") == latest_trade_date:
        # 快取資料是最新的，直接使用
        return cached_data
    
    # 快取資料過期或不存在，重新獲取
    fresh_data = fetch_futures_spread_data()
    if fresh_data:
        save_futures_spread_cache(fresh_data)
        return fresh_data
    
    # 如果無法獲取新資料，返回快取資料（如果有的話）
    return cached_data


def format_futures_spread_display(data: Dict[str, Any]) -> str:
    """格式化期現價差資料用於顯示"""
    if not data:
        return "❌ 無法獲取期現價差資料"
    
    def fmt_num(x: float) -> str:
        return f"{x:,.2f}"
    
    return f"""
**📅 日期:** {data['trade_date']}

**📊 價格資訊:**
- 加權股價指數: {fmt_num(data['spot_close'])}
- 台指期: {fmt_num(data['future_price'])}({data['future_near_month']}) 

**💰 期現價差:** {fmt_num(data['spread_pts'])} 點
"""