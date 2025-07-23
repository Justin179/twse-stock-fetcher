from analyze.analyze_price_break_conditions_dataloader import (
    get_today_prices, get_week_month_high_low, is_fubon_api_maintenance_time
)
from common.stock_loader import load_stock_list_with_names
import sys
from common.login_helper import get_logged_in_sdk

def detect_signals(file_path="my_stock_holdings.txt", sdk=None):
    attack_list = []
    weaken_list = []

    stocks, display_options = load_stock_list_with_names(file_path)
    id_name_map = {s.split()[0]: s.split()[1] for s in display_options if " " in s}


    for stock_id in stocks:
        try:
            today = get_today_prices(stock_id, sdk)
            w1, w2, m1, m2 = get_week_month_high_low(stock_id)
            c1 = today["c1"]

            if c1 is None:
                continue

            if w1 and m1 and c1 > w1 and c1 > m1:
                attack_list.append((stock_id, ["過上週高", "過上月高"]))
            if w2 and m2 and c1 < w2 and c1 < m2:
                weaken_list.append((stock_id, ["破上週低", "破上月低"]))

        except Exception as e:
            print(f"⚠️ {stock_id} 發生錯誤：{e}")

    return attack_list, weaken_list, id_name_map


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "my_stock_holdings.txt"

    
    if is_fubon_api_maintenance_time():
        print("🔧 現在是 API 維護時間，將使用資料庫資料")
        sdk = None
    else:
        try:
            sdk = get_logged_in_sdk()
        except Exception as e:
            print(f"⚠️ 登入失敗：{e}，改用資料庫資料")
            sdk = None    
    
    
    attack, weaken, id_name_map = detect_signals(file_path, sdk=sdk)

    print("\n📢 過上週高 且 過上月高（c1 > w1 且 c1 > m1）：")
    for stock_id, _ in attack:
        name = id_name_map.get(stock_id, "")
        print(f"✅ {stock_id} {name}")

    print("\n📉 破上週低 且 破上月低（c1 < w2 且 c1 < m2）：")
    for stock_id, _ in weaken:
        name = id_name_map.get(stock_id, "")
        print(f"❌ {stock_id} {name}")
    
    if sdk is not None:
        sdk.logout()

