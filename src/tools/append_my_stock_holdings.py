# tools/append_my_stock_holdings.py

import os

# 這一行會拿到目前這支 append_my_stock_holdings.py 的絕對路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 推回到專案根目錄（也就是再往上兩層）
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

# 組出完整路徑
holdings_path = os.path.join(ROOT_DIR, "my_stock_holdings.txt")
target_path = os.path.join(ROOT_DIR, "high_relative_strength_stocks.txt")


def read_stock_codes(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def append_holdings_to_target(holdings, target_file):
    with open(target_file, "a", encoding="utf-8") as f:
        f.write("\n# 持股清單\n")
        for code in holdings:
            f.write(f"{code}\n")

def remove_duplicates_but_keep_order_and_comments(target_file):
    seen = set()
    lines = []

    with open(target_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in reversed(lines):  # 從後面處理起
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
        elif stripped not in seen:
            seen.add(stripped)
            new_lines.append(line)
        # 重複的股票代碼就略過（不加入 new_lines）

    # 因為是從後面開始，所以需要再反轉回來
    new_lines.reverse()

    with open(target_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def main():
    holdings = read_stock_codes(holdings_path)
    append_holdings_to_target(holdings, target_path)
    remove_duplicates_but_keep_order_and_comments(target_path)
    print("✅ 已完成持股清單的追加與去重複處理。")

if __name__ == "__main__":
    main()
