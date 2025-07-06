import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.analyze.stock_conditions import apply_conditions
from src.ui.condition_selector import get_user_selected_conditions

use_gui = True  # or False for CLI/排程
conditions = get_user_selected_conditions(use_gui=use_gui)
# print("使用的條件：", conditions)


# 從命令列參數讀取乖離率門檻值，預設為 2
bias_threshold = float(sys.argv[1]) if len(sys.argv) > 1 else 2


def read_stock_list(file_path="shareholding_concentration_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
    stock_list = read_stock_list("shareholding_concentration_list.txt")
    all_report_rows = []
    missing_data_count = 0
    filtered_out_count = 0

    for stock_code in stock_list:
        try:
            input_hist = f"data/{stock_code}_history.csv"
            input_path = Path(input_hist)

            # ✅ 如果檔案不存在就跳過
            if not input_path.exists():
                missing_data_count += 1
                continue

            df = pd.read_csv(input_hist, index_col=0, parse_dates=True)
            df["MA5"] = df["Close"].rolling(window=5).mean()
            df["MA10"] = df["Close"].rolling(window=10).mean()
            df["MA24"] = df["Close"].rolling(window=24).mean()
            df["MA72"] = df["Close"].rolling(window=72).mean()
            df["MA200"] = df["Close"].rolling(window=200).mean()
            df[["MA5", "MA10", "MA24", "MA72", "MA200"]] = df[["MA5", "MA10", "MA24", "MA72", "MA200"]].round(2)
            df["Volume"] = (df["Volume"] / 1000).round().astype(int)


            # if stock_code == "2330":
            #     print(f"\n📊 {stock_code} 加入均線後的完整 df：")
            #     print(df)

            # 篩選條件
            df = apply_conditions(df, bias_threshold)

            # if stock_code == "1210":
            #     print(f"\n✅ {stock_code} 套用條件後的完整 df：")
            #     print(df)

            # 只取最後一行
            last_row = df.tail(1).copy()

            # 可以進入報告的條件 (因為使用 GUI 選擇條件，所以這裡註解掉)
            # conditions = {
            #     "站上上彎5日均 且乖離小": True,
            #     "均線排列正確 且開口小": True,
            #     "帶量跌": False,
            #     "帶量漲": True,
            #     "24日均乖離<15%": True
            # }

            # 未勾選就不處理、不過濾
            if all(last_row[col].iloc[0] == True for col, expected in conditions.items() if expected is True):
                last_row.insert(0, "Stock", stock_code)
                all_report_rows.append(last_row)
            else:
                filtered_out_count += 1  # 計算被篩選掉的股票數量

        except Exception as e:
            print(f"❌ {stock_code} 處理失敗: {e}")

    print(  # 📊 總覽
        f"📊 總覽：載入 {len(stock_list)} 檔，"
        f"遺失資料 {missing_data_count} 檔，"
        f"篩選排除 {filtered_out_count} 檔，"
        f"符合條件 {len(all_report_rows)} 檔"
    )

    if all_report_rows:
        report_df = pd.concat(all_report_rows, ignore_index=True)
        Path("output").mkdir(parents=True, exist_ok=True)
        report_df.to_csv("output/all_report.csv", index=False, encoding="utf-8-sig")

        # 產生 XQ 匯入清單
        xq_list = report_df["Stock"].astype(str) + ".TW"
        xq_path = Path("output") / "匯入XQ.csv"
        xq_list.to_csv(xq_path, index=False, header=False, encoding="utf-8-sig")
        print(  # 📁 輸出
            f"📁 報表輸出：all_report.csv（{bias_threshold}%），"
            f"XQ 匯入：匯入XQ.csv（共 {len(xq_list)} 檔）"
        )
        print()  # 空一行