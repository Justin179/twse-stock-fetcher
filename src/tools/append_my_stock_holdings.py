# tools/append_my_stock_holdings.py

import os

# 這一行會拿到目前這支 append_my_stock_holdings.py 的絕對路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 推回到專案根目錄（也就是再往上兩層）
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

# 組出完整路徑
holdings_path = os.path.join(ROOT_DIR, "my_stock_holdings.txt")
hermits_path = os.path.join(ROOT_DIR, "periodically_updated_stock_lists", "Hermits_stock_picks.txt")
inst_revenue_path = os.path.join(ROOT_DIR, "periodically_updated_stock_lists", "institutional_revenue_forecast_this_year.txt")
target_path = os.path.join(ROOT_DIR, "high_relative_strength_stocks.txt")


def read_stock_codes(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def merge_and_deduplicate_and_sort(sources, target_file):
    all_codes = set()
    for src in sources:
        all_codes.update(read_stock_codes(src))

    # 排序 (從小到大)
    sorted_codes = sorted(all_codes)

    with open(target_file, "w", encoding="utf-8") as f:
        for code in sorted_codes:
            f.write(f"{code}\n")


def main():
    sources = [holdings_path, hermits_path, inst_revenue_path]
    merge_and_deduplicate_and_sort(sources, target_path)
    print("✅ 已完成多清單合併、去重、排序，結果已寫入 high_relative_strength_stocks.txt。")


if __name__ == "__main__":
    main()
