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
from analyze.moving_average_weekly import is_price_above_upward_wma5


def detect_signals_and_uptrends_unified(stocks, id_name_map, sdk=None):
    """
    統一對合併後的去重個股清單進行一次性的 Fubon API 呼叫、趨勢與跌破判斷。
    """
    uptrend_list = []
    weaken_list = []

    print(f"\n🔍 開始在一線流程中，檢測 {len(stocks)} 檔去重股票的「向上趨勢 4 條件」與「跌破訊號」...")
    
    for i, stock_id in enumerate(stocks, 1):
        try:
            print(f"⏳ ({i}/{len(stocks)}) 處理 {stock_id}...")
            
            # 取得今日價格資訊（只呼叫一次 API！）
            today = get_today_prices(stock_id, sdk)
            today_date = today["date"]
            c1 = today["c1"]

            if c1 is None:
                print(f"⚠️ {stock_id} 無法取得現價，跳過")
                continue

            # 取得週月高低點
            w1, w2, m1, m2 = get_week_month_high_low(stock_id)

            # A. 向上趨勢所需均線計算（含今日現價）
            ma5 = compute_ma_with_today(stock_id, today_date, c1, 5)
            ma10 = compute_ma_with_today(stock_id, today_date, c1, 10)
            ma24 = compute_ma_with_today(stock_id, today_date, c1, 24)
            
            # 判斷是否站上上彎5週均線
            above_upward_wma5 = is_price_above_upward_wma5(stock_id, today_date, c1, debug_print=False)

            # B. 判斷是否符合向上趨勢的 4 大嚴格條件
            if is_uptrending_now(stock_id, today_date, c1, w1, m1, ma5, ma10, ma24, above_upward_wma5):
                uptrend_list.append(stock_id)
                print(f"📈 {stock_id} 符合向上趨勢訊號")

            # C. 判斷是否符合跌破訊號 (破上週低且破上月低)
            if w2 and m2 and c1 < w2 and c1 < m2:
                weaken_list.append(stock_id)
                print(f"❌ {stock_id} 跌破訊號")

        except KeyboardInterrupt:
            print(f"\n🛑 用戶中斷，已處理 {i-1}/{len(stocks)} 檔股票")
            break
        except Exception as e:
            print(f"⚠️ {stock_id} 發生錯誤：{e}")
            continue

    return uptrend_list, weaken_list


if __name__ == "__main__":
    file_path1 = sys.argv[1] if len(sys.argv) > 1 else "my_stock_holdings.txt"
    file_path2 = "shareholding_concentration_list.txt"
    bias_threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0  # 新增乖離率參數

    print(f"📊 開始突破暨趨勢訊號檢測...")
    print(f"📁 預設清單一：{file_path1}")
    print(f"📁 預設清單二：{file_path2}")
    print(f"📈 乖離率門檻：{bias_threshold}%")

    # 1. 讀取並合併兩個清單，進行去重
    try:
        stocks1, display_options1 = load_stock_list_with_names(file_path1)
        stocks2, display_options2 = load_stock_list_with_names(file_path2)
    except Exception as e:
        print(f"❌ 讀取清單失敗：{e}")
        sys.exit(1)

    # 建立統一名稱對照表
    id_name_map = {}
    for s in display_options1 + display_options2:
        if " " in s:
            parts = s.split()
            id_name_map[parts[0]] = parts[1]

    # 合併並去除重複
    merged_stocks = list(dict.fromkeys(stocks1 + stocks2))
    print(f"📋 清單一數量：{len(stocks1)} 檔")
    print(f"📋 清單二數量：{len(stocks2)} 檔")
    print(f"📋 兩清單合併去重後總數：{len(merged_stocks)} 檔")

    # 2. 登入富邦 API
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
        # 3. 統一走一線程序，只連線一次 API 抓取現價
        uptrend_list, weaken_list = detect_signals_and_uptrends_unified(merged_stocks, id_name_map, sdk=sdk)

        print(f"\n📋 符合4大向上趨勢條件股票：{len(uptrend_list)} 檔")

        # 4. 多加一層 GUI 條件篩選器
        print(f"\n🔍 對 {len(uptrend_list)} 檔符合趨勢的股票進行第二輪條件篩選...")
        filtered_stocks = filter_attack_stocks(uptrend_list, bias_threshold=bias_threshold)
        filtered_set = set(filtered_stocks)

        print("\n📢 符合向上趨勢之個股清單（一篩與二篩結果）：")
        if uptrend_list:
            for stock_id in uptrend_list:
                name = id_name_map.get(stock_id, "")
                if stock_id in filtered_set:
                    print(f"✅ {stock_id} {name} [通過二篩] (過高且向上趨勢)")
                else:
                    print(f"ℹ️ {stock_id} {name} [僅過一篩]")
        else:
            print("ℹ️ 無符合條件的股票")

        # === 寫成 籌碼集中且趨勢向上.csv ===
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

        # 5. 輸出跌破結果
        print("\n📉 現價 破上週低 且 破上月低（c1 < w2 且 c1 < m2）：")
        if weaken_list:
            for stock_id in weaken_list:
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
