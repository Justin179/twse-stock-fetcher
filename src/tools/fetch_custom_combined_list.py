import os
import re
import sys
import requests
import urllib3
import pandas as pd
import yfinance as yf
import sqlite3
from datetime import datetime, timedelta

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Ensure terminal prints UTF-8 characters correctly
sys.stdout.reconfigure(encoding='utf-8')

# Paths
DB_PATH = "data/institution.db"
OUTPUT_PATH = "high_relative_strength_stocks.txt"

# Standard 0050 (元大台灣50) complete constituent fallback list (top 50 companies)
# In case of API failure or limited top holdings, this provides complete covering.
STANDARD_0050_CONSTITUENTS = [
    "2330", "2317", "2454", "2308", "2382", "2881", "2882", "3711", "2891", "2301",
    "2886", "2884", "2892", "2885", "5880", "1216", "2002", "2324", "2303", "2890",
    "3231", "2883", "1101", "2603", "3045", "2912", "2357", "3037", "2609", "2618",
    "2408", "1102", "2356", "4958", "2610", "2615", "2379", "2880", "1301", "1303",
    "2409", "3481", "6505", "1326", "2352", "1402", "1504", "2633", "9904", "2371"
]


def clean_stock_code(raw_code):
    """
    Cleans stock tickers of suffix `.TW`, `.TWO` and filters out anything that
    is not a standard 4-digit Taiwan Stock.
    """
    if not raw_code:
        return None
    code = str(raw_code).strip().upper()
    # Strip .TW, .TWO suffixes
    code = re.sub(r'\.TW[O]?$', '', code)
    # Check if it matches exactly a 4-digit Taiwan stock code
    if re.match(r'^\d{4}$', code):
        return code
    return None


def fetch_etf_holdings_via_yfinance(etf_symbol):
    """
    Fetch ETF top holdings using yfinance.
    """
    print(f"🔍 正在透過 Yahoo Finance 獲取 {etf_symbol} 的熱門持股...")
    try:
        ticker = yf.Ticker(etf_symbol)
        holdings_df = ticker.funds_data.top_holdings
        if holdings_df is not None and not holdings_df.empty:
            symbols = list(holdings_df.index)
            cleaned_codes = []
            for sym in symbols:
                cleaned = clean_stock_code(sym)
                if cleaned:
                    cleaned_codes.append(cleaned)
            print(f"      🗂️ {etf_symbol} 獲取成功！取得 {len(cleaned_codes)} 檔有效的台股成分股。")
            return cleaned_codes
        else:
            print(f"      ⚠️ {etf_symbol} 的 holdings 回傳為空。")
    except Exception as e:
        print(f"      ❌ 解析 {etf_symbol} 時發生錯誤: {e}")
    return []


def get_volume_leaders_from_db(top_n=50):
    """
    備援方案：從在地資料庫讀取最新成交量排行。
    """
    print("   ⚠️ 網路獲取失敗或逾時，嘗試從在地資料庫讀取最新成交量排行...")
    try:
        conn = sqlite3.connect(DB_PATH)
        # 找出資料庫中最新的日期
        latest_date_df = pd.read_sql_query("SELECT MAX(date) as max_date FROM twse_prices", conn)
        latest_date = latest_date_df.iloc[0]["max_date"]
        
        if not latest_date:
            print("   ❌ 資料庫中查無資料。")
            return []
            
        print(f"   📅 使用資料庫最新日期: {latest_date}")
        query = """
            SELECT stock_id 
            FROM twse_prices 
            WHERE date = ? 
            ORDER BY volume DESC 
            LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(latest_date, top_n))
        conn.close()
        
        leaders = df["stock_id"].tolist()
        if leaders:
            print(f"   ✅ 成功從資料庫取得 {len(leaders)} 檔成交量熱門股。")
        return leaders
    except Exception as e:
        print(f"   ❌ 資料庫讀取失敗: {e}")
        return []


def get_latest_twse_volume_leaders(top_n=50):
    """
    Search backwards from today to locate the latest trading day on TWSE,
    then fetch MI_INDEX and sort to get the top `top_n` volume leaders.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.twse.com.tw/zh/page/trading/exchange/MI_INDEX.html"
    }
    
    print("🔍 正在尋找最新的證交所開盤日行情資料...")
    date_to_try = datetime.today()
    # 縮短嘗試天數與逾時時間，若失敗立即轉向資料庫備援
    for _ in range(3): 
        date_str = date_to_try.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={date_str}&type=ALLBUT0999"
        try:
            r = requests.get(url, headers=headers, verify=False, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if "tables" in data and len(data["tables"]) > 8:
                    table8 = data["tables"][8]
                    title = table8.get("title", "")
                    rows_data = table8.get("data", [])
                    
                    print(f"   🎉 成功找到最近收盤日資料！日期：{date_to_try.strftime('%Y-%m-%d')} ({title[:15]}...)")
                    
                    code_idx = 0
                    val_idx = 2
                    stock_volumes = []
                    for row in rows_data:
                        raw_code = row[code_idx]
                        clean_code = clean_stock_code(raw_code)
                        if clean_code:
                            try:
                                # Parsing format e.g. "12,345,678"
                                vol_str = row[val_idx].replace(",", "")
                                vol = int(vol_str)
                                stock_volumes.append((clean_code, vol))
                            except ValueError: continue
                    
                    # Sort by volume descending
                    stock_volumes.sort(key=lambda x: x[1], reverse=True)
                    top_leaders = [item[0] for item in stock_volumes[:top_n]]
                    print(f"   📊 成功取得成交量排行前 {len(top_leaders)} 的個股清單。")
                    return top_leaders
        except Exception:
            pass
        date_to_try -= timedelta(days=1)
        
    return get_volume_leaders_from_db(top_n)


def main():
    print("==================================================")
    print("🚀 開始執行台股多訊候選池產出工具 (0050/主動ETF/高成交量)")
    print("==================================================")

    # 1. Fetch ETF holdings
    holdings_0050 = fetch_etf_holdings_via_yfinance("0050.TW")
    holdings_00981a = fetch_etf_holdings_via_yfinance("00981A.TW")
    holdings_00992a = fetch_etf_holdings_via_yfinance("00992A.TW")

    # 2. Get standard 0050 fallback constituents
    all_0050 = list(dict.fromkeys(holdings_0050 + STANDARD_0050_CONSTITUENTS))
    print(f"💡 整合 0050 自訂基準成分股，共計 {len(all_0050)} 檔。")

    # 3. Fetch Top 50 Daily Trading Volumes
    volume_leaders = get_latest_twse_volume_leaders(top_n=50)

    # 4. Integrate and deduplicate
    # Sequence of priority: 0050 constituents, active ETFs, volume leaders
    combined_stocks = []
    combined_stocks.extend(all_0050)
    combined_stocks.extend(holdings_00981a)
    combined_stocks.extend(holdings_00992a)
    combined_stocks.extend(volume_leaders)

    # Remove duplicates while preserving original sequence order
    final_stock_list = list(dict.fromkeys(combined_stocks))

    print("==================================================")
    print("📊 統計結果：")
    print(f"   └─ 0050 整合成分股數: {len(all_0050)} 檔")
    print(f"   └─ 00981A 核心成分股數: {len(holdings_00981a)} 檔")
    print(f"   └─ 00992A 核心成分股數: {len(holdings_00992a)} 檔")
    print(f"   └─ 當日成交量排行前50: {len(volume_leaders)} 檔")
    print(f"   👉 總計去重合併後股票數: {len(final_stock_list)} 檔")
    print("==================================================")

    if not final_stock_list:
        print("❌ 未取得任何有效股票代號，終止寫入運作。")
        sys.exit(1)

    # 5. Read existing stocks from high_relative_strength_stocks.txt and append new ones (with deduplication and sorting)
    try:
        existing_stocks = []
        if os.path.exists(OUTPUT_PATH):
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_stocks = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        # Merge existing stocks with the newly fetched ones, sorting alphabetically
        merged_all_stocks = sorted(list(set(existing_stocks + final_stock_list)))
        
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            for stock in merged_all_stocks:
                f.write(f"{stock}\n")
        print(f"💾 成果（新增 0050、主動 ETF、熱門成分股）已成功合併並排序寫入至：[{OUTPUT_PATH}]")
        print(f"📊 目前 [{OUTPUT_PATH}] 總股票檔數：{len(merged_all_stocks)} 檔")
    except Exception as e:
        print(f"❌ 寫入目標檔案 {OUTPUT_PATH} 失敗: {e}")


if __name__ == "__main__":
    main()
