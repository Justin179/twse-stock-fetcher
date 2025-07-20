from analyze.analyze_price_break_conditions_dataloader import (
    get_today_prices, get_week_month_high_low
)
from common.stock_loader import load_stock_list_with_names
import sys


def detect_signals(file_path="my_stock_holdings.txt"):
    attack_list = []
    weaken_list = []

    stocks, _ = load_stock_list_with_names(file_path)

    for stock_id in stocks:
        try:
            today = get_today_prices(stock_id)
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

    return attack_list, weaken_list


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "my_stock_holdings.txt"
    attack, weaken = detect_signals(file_path)

    print("\n📢 有進攻訊號的個股（c1 > w1 且 c1 > m1）：")
    for stock_id, tags in attack:
        print(f"✅ {stock_id} {'、'.join(tags)}")

    print("\n📉 有轉弱訊號的個股（c1 < w2 且 c1 < m2）：")
    for stock_id, tags in weaken:
        print(f"❌ {stock_id} {'、'.join(tags)}")
