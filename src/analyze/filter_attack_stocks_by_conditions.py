import sqlite3
from pathlib import Path

from src.analyze.calculate_weekly_ma import calculate_weekly_ma
from src.analyze.stock_conditions import apply_conditions
from src.common.db_helpers import fetch_stock_history_from_db
from src.ui.condition_selector import get_user_selected_conditions

# 程式中多加一層條件篩選器，回傳符合條件的個股清單

def filter_attack_stocks(attack: list[str], bias_threshold: float = 3.0) -> list[str]:
    """
    對 attack 清單內的個股代碼執行條件篩選，回傳篩選後的個股清單（不加.TW 後綴）
    """
    if not attack:
        return []

    # 🧠 自動轉換 tuple -> stock_id
    if isinstance(attack[0], tuple):
        attack = [item[0] for item in attack]

    custom_conditions = {
        "收盤價站上 上彎5日均 且乖離小": True,
        "5 10多頭排列 均線上彎 開口小": True,
        "10 24多頭排列 均線上彎 開口小": False,
        "24日均乖離<15%": True,
        "量價同步": False,
        "收盤價站上上彎5週均": True,
        "站上上彎72日均": False
    }
    use_gui = True
    conditions = get_user_selected_conditions(
        use_gui=use_gui, default_conditions=custom_conditions, bias_threshold=bias_threshold)

    db_path = str(Path.cwd() / "data" / "institution.db")
    filtered_stocks = []
    rejected_stocks = []

    with sqlite3.connect(db_path) as conn:
        for stock_code in attack:
            try:
                print(f"\n🧪 篩選中: {stock_code}")
                df = fetch_stock_history_from_db(conn, stock_code)

                if df.empty or len(df) < 200:
                    print(f"⚠️ {stock_code} 資料不足（筆數：{len(df)}）")
                    continue

                df["MA5"] = df["Close"].rolling(window=5).mean()
                df["MA10"] = df["Close"].rolling(window=10).mean()
                df["MA24"] = df["Close"].rolling(window=24).mean()
                df["MA72"] = df["Close"].rolling(window=72).mean()
                df["MA200"] = df["Close"].rolling(window=200).mean()

                weekly_ma5 = calculate_weekly_ma(df, weeks=5)
                df["WMA5"] = df.index.map(weekly_ma5["WMA5"])
                df[["MA5", "MA10", "MA24", "MA72", "MA200"]] = df[
                    ["MA5", "MA10", "MA24", "MA72", "MA200"]
                ].round(2)
                df["Volume"] = (df["Volume"] / 1000).round().astype(int)

                df = apply_conditions(df, bias_threshold)
                last_row = df.tail(1).copy()

                if all(last_row[col].iloc[0] == True for col, expected in conditions.items() if expected is True):
                    filtered_stocks.append(stock_code)
                else:
                    rejected_stocks.append(stock_code)

            except Exception as e:
                print(f"❌ {stock_code} 處理失敗: {e}")

    if rejected_stocks:
        print("\n🚫 以下個股未通過篩選條件：")
        print("、".join(rejected_stocks))

    return filtered_stocks
