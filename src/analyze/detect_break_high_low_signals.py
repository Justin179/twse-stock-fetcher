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
    bias_threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0  # 新增乖離率參數

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

    # 多加一層條件篩選
    attack = filter_attack_stocks(attack, bias_threshold=bias_threshold)  # 這裡的 attack 會是 [stock_id, ...]


    print("\n📢 現價 過上週高 且 過上月高（c1 > w1 且 c1 > m1）：")
    for stock_id in attack:
        name = id_name_map.get(stock_id, "")
        print(f"✅ {stock_id} {name}")

    # === 新增：將 attack 清單加 .TW 後，直接寫成 過上週上月高個股.csv ===
    try:
        if attack:
            Path("output").mkdir(parents=True, exist_ok=True)
            out_path = Path("output") / "過上週上月高個股.csv"
            out_series = pd.Series([f"{sid}.TW" for sid in attack])
            out_series.to_csv(out_path, index=False, header=False, encoding="utf-8-sig")
            print(f"📁 已將 {len(out_series)} 檔 attack 清單輸出至 {out_path}")
        else:
            print("ℹ️ attack 清單為空，未產生輸出檔。")
    except Exception as e:
        print(f"⚠️ 輸出檔案時發生錯誤：{e}")

    print("\n📉 現價 破上週低 且 破上月低（c1 < w2 且 c1 < m2）：")
    for stock_id, _ in weaken:
        name = id_name_map.get(stock_id, "")
        print(f"❌ {stock_id} {name}")

    if sdk is not None:
        sdk.logout()
