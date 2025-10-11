from analyze.analyze_price_break_conditions_dataloader import (
    get_today_prices, get_week_month_high_low, is_fubon_api_maintenance_time
)
from common.stock_loader import load_stock_list_with_names
import sys
from common.login_helper import get_logged_in_sdk
from analyze.filter_attack_stocks_by_conditions import filter_attack_stocks

# 新增匯出所需
from pathlib import Path
import pandas as pd

# 新增趨勢判斷所需
from ui.price_break_display_module import is_uptrending_now, compute_ma_with_today


def detect_signals(file_path="my_stock_holdings.txt", sdk=None):
    attack_list = []
    weaken_list = []

    stocks, display_options = load_stock_list_with_names(file_path)
    id_name_map = {s.split()[0]: s.split()[1] for s in display_options if " " in s}

    print(f"🔍 開始檢測 {len(stocks)} 檔股票的突破訊號...")
    
    for i, stock_id in enumerate(stocks, 1):
        try:
            print(f"⏳ ({i}/{len(stocks)}) 處理 {stock_id}...")
            today = get_today_prices(stock_id, sdk)
            w1, w2, m1, m2 = get_week_month_high_low(stock_id)
            c1 = today["c1"]

            if c1 is None:
                print(f"⚠️ {stock_id} 無法取得現價，跳過")
                continue

            if w1 and m1 and c1 > w1 and c1 > m1:
                attack_list.append((stock_id, ["過上週高", "過上月高"]))
                print(f"✅ {stock_id} 突破訊號")
            if w2 and m2 and c1 < w2 and c1 < m2:
                weaken_list.append((stock_id, ["破上週低", "破上月低"]))
                print(f"❌ {stock_id} 跌破訊號")

        except KeyboardInterrupt:
            print(f"\n🛑 用戶中斷，已處理 {i-1}/{len(stocks)} 檔股票")
            break
        except Exception as e:
            print(f"⚠️ {stock_id} 發生錯誤：{e}")
            continue

    return attack_list, weaken_list, id_name_map


def detect_uptrending_stocks(file_path="shareholding_concentration_list.txt", sdk=None):
    """
    檢測向上趨勢的個股
    讀取 shareholding_concentration_list.txt，找出符合向上趨勢條件的股票
    """
    uptrend_list = []
    
    stocks, display_options = load_stock_list_with_names(file_path)
    id_name_map = {s.split()[0]: s.split()[1] for s in display_options if " " in s}
    
    print(f"\n🔍 開始檢測 {len(stocks)} 檔股票的向上趨勢...")
    
    for i, stock_id in enumerate(stocks, 1):
        try:
            print(f"⏳ ({i}/{len(stocks)}) 處理 {stock_id}...")
            
            # 取得今日價格資訊
            today = get_today_prices(stock_id, sdk)
            today_date = today["date"]
            c1 = today["c1"]
            
            if c1 is None:
                print(f"⚠️ {stock_id} 無法取得現價，跳過")
                continue
            
            # 取得週月高低點
            w1, w2, m1, m2 = get_week_month_high_low(stock_id)
            
            # 計算均線（含今日現價）
            ma5 = compute_ma_with_today(stock_id, today_date, c1, 5)
            ma10 = compute_ma_with_today(stock_id, today_date, c1, 10)
            ma24 = compute_ma_with_today(stock_id, today_date, c1, 24)
            
            # 判斷是否為向上趨勢
            if is_uptrending_now(stock_id, today_date, c1, w1, m1, ma5, ma10, ma24):
                uptrend_list.append((stock_id, ["向上趨勢"]))
                print(f"📈 {stock_id} 向上趨勢訊號")
            
        except KeyboardInterrupt:
            print(f"\n🛑 用戶中斷，已處理 {i-1}/{len(stocks)} 檔股票")
            break
        except Exception as e:
            print(f"⚠️ {stock_id} 發生錯誤：{e}")
            continue
    
    return uptrend_list, id_name_map


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "my_stock_holdings.txt"
    bias_threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0  # 新增乖離率參數

    print(f"📊 開始突破訊號檢測...")
    print(f"📁 股票清單：{file_path}")
    print(f"📈 乖離率門檻：{bias_threshold}%")

    if is_fubon_api_maintenance_time():
        print("🔧 現在是 API 維護時間，將使用資料庫資料")
        sdk = None
    else:
        try:
            print("🚪 嘗試登入富邦 API...")
            sdk = get_logged_in_sdk()
            print("✅ 登入成功")
        except Exception as e:
            print(f"⚠️ 登入失敗：{e}，改用資料庫資料")
            sdk = None

    try:
        attack, weaken, id_name_map = detect_signals(file_path, sdk=sdk)

        # 檢測向上趨勢股票（從 shareholding_concentration_list.txt）
        print(f"\n📊 檢測籌碼集中且向上趨勢的股票...")
        uptrend, uptrend_id_name_map = detect_uptrending_stocks("shareholding_concentration_list.txt", sdk=sdk)
        
        # 更新 id_name_map（合併兩個清單的股票名稱對應）
        id_name_map.update(uptrend_id_name_map)
        
        # 合併突破股票與向上趨勢股票
        attack_stock_ids = [stock_id for stock_id, _ in attack]
        uptrend_stock_ids = [stock_id for stock_id, _ in uptrend]
        
        # 匯集並去重
        combined_stock_ids = list(set(attack_stock_ids + uptrend_stock_ids))
        print(f"\n📋 突破股票：{len(attack_stock_ids)} 檔")
        print(f"📋 向上趨勢股票：{len(uptrend_stock_ids)} 檔")
        print(f"📋 合併後（去重）：{len(combined_stock_ids)} 檔")

        # 多加一層條件篩選
        print(f"\n🔍 對 {len(combined_stock_ids)} 檔股票進行條件篩選...")
        # 將 combined_stock_ids 轉換為 filter_attack_stocks 需要的格式
        combined_tuples = [(stock_id, []) for stock_id in combined_stock_ids]
        filtered_stocks = filter_attack_stocks(combined_tuples, bias_threshold=bias_threshold)

        print("\n📢 現價 過上週高 且 過上月高 或 向上趨勢（篩選後）：")
        if filtered_stocks:
            for stock_id in filtered_stocks:
                name = id_name_map.get(stock_id, "")
                # 判斷是來自突破還是向上趨勢
                source = []
                if stock_id in attack_stock_ids:
                    source.append("突破")
                if stock_id in uptrend_stock_ids:
                    source.append("向上趨勢")
                source_str = "+".join(source)
                print(f"✅ {stock_id} {name} ({source_str})")
        else:
            print("ℹ️ 無符合條件的股票")

        # === 將篩選後的清單加 .TW 後，寫成 籌碼集中且趨勢向上.csv ===
        try:
            if filtered_stocks:
                Path("output").mkdir(parents=True, exist_ok=True)
                out_path = Path("output") / "籌碼集中且趨勢向上.csv"
                out_series = pd.Series([f"{sid}.TW" for sid in filtered_stocks])
                out_series.to_csv(out_path, index=False, header=False, encoding="utf-8-sig")
                print(f"📁 已將 {len(out_series)} 檔股票清單輸出至 {out_path}")
            else:
                print("ℹ️ 篩選後清單為空，未產生輸出檔。")
        except Exception as e:
            print(f"⚠️ 輸出檔案時發生錯誤：{e}")

        print("\n📉 現價 破上週低 且 破上月低（c1 < w2 且 c1 < m2）：")
        if weaken:
            for stock_id, _ in weaken:
                name = id_name_map.get(stock_id, "")
                print(f"❌ {stock_id} {name}")
        else:
            print("ℹ️ 無符合條件的跌破股票")

    except KeyboardInterrupt:
        print("\n🛑 程式被用戶中斷")
    except Exception as e:
        print(f"\n💥 程式執行發生錯誤：{e}")
    finally:
        if sdk is not None:
            try:
                sdk.logout()
                print("🚪 已登出富邦 API")
            except:
                pass
