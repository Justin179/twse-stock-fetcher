import pandas as pd
from pathlib import Path
import sys
from stock_conditions import apply_conditions


# 從命令列參數讀取乖離率門檻值，預設為 3
bias_threshold = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0


def read_stock_list(file_path="stock_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
    stock_list = read_stock_list("stock_list.txt")
    all_report_rows = []

    for stock_code in stock_list:
        try:
            input_hist = f"data/{stock_code}_history.csv"

            df = pd.read_csv(input_hist, index_col=0, parse_dates=True)
            df["MA5"] = df["Close"].rolling(window=5).mean()
            df["MA10"] = df["Close"].rolling(window=10).mean()
            df["MA24"] = df["Close"].rolling(window=24).mean()
            df[["MA5", "MA10", "MA24"]] = df[["MA5", "MA10", "MA24"]].round(1)
            df["Volume"] = (df["Volume"] / 1000).round().astype(int)


            # if stock_code == "1210":
            #     print(f"\n📊 {stock_code} 加入均線後的完整 df：")
            #     print(df)

            # 篩選條件
            df = apply_conditions(df, bias_threshold)

            # if stock_code == "1210":
            #     print(f"\n✅ {stock_code} 套用條件後的完整 df：")
            #     print(df)

            # 只取最後一行
            last_row = df.tail(1).copy()

            # 可以進入報告的條件
            conditions = {
                "站上5日均 且乖離小": True,
                "均線排列正確 且開口小": True,
                "帶量跌": False
            }
            if all(last_row[col].iloc[0] == expected for col, expected in conditions.items()):
                last_row.insert(0, "Stock", stock_code)
                all_report_rows.append(last_row)


        except Exception as e:
            print(f"❌ {stock_code} 處理失敗: {e}")

    if all_report_rows:
        report_df = pd.concat(all_report_rows, ignore_index=True)
        Path("output").mkdir(parents=True, exist_ok=True)
        report_df.to_csv("output/all_report.csv", index=False, encoding="utf-8-sig")
        print(f"📊 已輸出整併報告（乖離條件 < {bias_threshold}%）：output/all_report.csv")
