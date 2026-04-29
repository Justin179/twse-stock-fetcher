import os
import json
import sqlite3
import subprocess
import math
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any


logger = logging.getLogger(__name__)
_last_futures_spread_status = {"level": "info", "message": ""}


def _set_futures_spread_status(message: str = "", level: str = "info") -> None:
    global _last_futures_spread_status
    _last_futures_spread_status = {"level": level, "message": message}

    if not message:
        return

    log_message = f"[futures_spread] {message}"
    if level == "error":
        logger.error(log_message)
    elif level == "warning":
        logger.warning(log_message)
    else:
        logger.info(log_message)


def get_futures_spread_status() -> Dict[str, str]:
    """回傳最近一次期現價差抓取狀態，供 UI 顯示 debug 提示。"""
    return dict(_last_futures_spread_status)

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
    except Exception as e:
        _set_futures_spread_status(f"讀取期現價差快取失敗：{e}", "warning")
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


def _is_valid_futures_spread_data(data: Optional[Dict[str, Any]]) -> bool:
    """檢查期現價差資料是否完整且數值有效。"""
    if not isinstance(data, dict):
        return False

    required_keys = ("trade_date", "spot_close", "future_near_month", "future_price", "spread_pts")
    if any(key not in data for key in required_keys):
        return False

    if not data.get("trade_date") or not data.get("future_near_month"):
        return False

    for key in ("spot_close", "future_price", "spread_pts"):
        try:
            value = float(data[key])
        except (TypeError, ValueError):
            return False
        if not math.isfinite(value):
            return False

    return True


def _get_invalid_futures_spread_reason(data: Optional[Dict[str, Any]]) -> str:
    if not isinstance(data, dict):
        return "回傳資料不是 dict"

    required_keys = ("trade_date", "spot_close", "future_near_month", "future_price", "spread_pts")
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        return f"缺少欄位：{', '.join(missing_keys)}"

    if not data.get("trade_date"):
        return "trade_date 為空"
    if not data.get("future_near_month"):
        return "future_near_month 為空"

    for key in ("spot_close", "future_price", "spread_pts"):
        try:
            value = float(data[key])
        except (TypeError, ValueError):
            return f"{key} 無法轉成數字：{data[key]}"
        if not math.isfinite(value):
            return f"{key} 不是有效有限數值：{data[key]}"

    return "未知格式錯誤"

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
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                _set_futures_spread_status(f"期現價差子程序輸出不是合法 JSON：{e}", "error")
                return None

            if _is_valid_futures_spread_data(data):
                return data

            _set_futures_spread_status(
                f"期現價差資料格式異常：{_get_invalid_futures_spread_reason(data)}",
                "error",
            )
            return None

        stderr = (result.stderr or "").strip().splitlines()
        stderr_tail = stderr[-1] if stderr else "無 stderr 訊息"
        _set_futures_spread_status(f"期現價差子程序執行失敗（code={result.returncode}）：{stderr_tail}", "error")
        return None
    except Exception as e:
        _set_futures_spread_status(f"執行期現價差程式出錯：{e}", "error")
        return None


def get_futures_spread_info() -> Optional[Dict[str, Any]]:
    """
    獲取期現價差資訊（智慧快取）
    先檢查快取，如果資料不是最新交易日的就重新獲取
    """
    # 確保 data 目錄存在
    os.makedirs("data", exist_ok=True)
    _set_futures_spread_status()
    
    latest_trade_date = get_latest_trade_date_from_db()
    if not latest_trade_date:
        # 如果無法獲取最新交易日，直接獲取新資料
        data = fetch_futures_spread_data()
        if data:
            save_futures_spread_cache(data)
            _set_futures_spread_status("無法從 DB 判斷最新交易日，已直接抓取最新期現價差資料。", "warning")
        return data
    
    # 檢查快取
    cached_data = load_futures_spread_cache()
    cached_is_valid = _is_valid_futures_spread_data(cached_data)

    # 👇 這裡比對日期：檢查快取資料的交易日是否等於最新交易日
    if cached_is_valid and cached_data.get("trade_date") == latest_trade_date:
        # 快取資料是最新的，直接使用
        return cached_data

    if cached_data and not cached_is_valid:
        _set_futures_spread_status(
            f"忽略失效快取資料：{_get_invalid_futures_spread_reason(cached_data)}，改為重新抓取。",
            "warning",
        )
    
    # 快取資料過期或不存在，重新獲取
    fresh_data = fetch_futures_spread_data()
    if _is_valid_futures_spread_data(fresh_data):
        save_futures_spread_cache(fresh_data)
        if cached_data and not cached_is_valid:
            _set_futures_spread_status("已忽略失效快取並重新抓回最新期現價差資料。", "warning")
        elif cached_is_valid and cached_data.get("trade_date") != latest_trade_date:
            _set_futures_spread_status(
                f"期現價差快取日期 {cached_data.get('trade_date')} 已過期，已更新為 {fresh_data.get('trade_date')}。",
                "warning",
            )
        return fresh_data
    
    # 如果無法獲取新資料，返回快取資料（如果有的話）
    if cached_is_valid:
        _set_futures_spread_status(
            f"重新抓取期現價差失敗，暫時改用快取 {cached_data.get('trade_date')} 的資料。",
            "warning",
        )
        return cached_data

    return None


def format_futures_spread_display(data: Dict[str, Any]) -> str:
    """格式化期現價差資料用於顯示"""
    if not _is_valid_futures_spread_data(data):
        return "❌ 無法獲取期現價差資料"
    
    def fmt_num(x: float) -> str:
        return f"{x:,.2f}"
    
    def get_market_sentiment(spread_pts: float) -> str:
        """根據期現價差判斷市場情緒"""
        if spread_pts >= 100:
            return "🔥 市場情緒太樂觀，開高容易拉回，開低容易拉高"
        elif spread_pts >= 6:
            return "😊 市場情緒樂觀"
        elif spread_pts >= -5:
            return "😐 市場情緒中立"
        else:
            return "😰 市場情緒悲觀"
    
    sentiment = get_market_sentiment(data['spread_pts'])
    
    return f"""
**📅 日期:** {data['trade_date']}

**📊 價格資訊:**
- 加權股價指數: {fmt_num(data['spot_close'])}
- 台指期: {fmt_num(data['future_price'])}({data['future_near_month']}) 

**💰 期現價差:** {fmt_num(data['spread_pts'])} 點

**🎯 市場解讀:** {sentiment}
"""