import pandas as pd
from pathlib import Path


def read_stock_list(file_path="stock_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
    stock_list = read_stock_list("stock_list.txt")
    all_report_rows = []   # 最終符合條件的資料彙整

    for stock_code in stock_list:
        try:
            input_hist = f"data/{stock_code}_history.csv"

            # 計算均線
            df = pd.read_csv(input_hist, index_col=0, parse_dates=True)
            df["MA5"] = df["Close"].rolling(window=5).mean()
            df["MA10"] = df["Close"].rolling(window=10).mean()
            df["MA24"] = df["Close"].rolling(window=24).mean()
            df[["MA5", "MA10", "MA24"]] = df[["MA5", "MA10", "MA24"]].round(1)
            df["Volume"] = (df["Volume"] / 1000).round().astype(int)

            # 條件分析
            df["站上5日均 且乖離小"] = df.apply(
                lambda row: round((row["Close"] - row["MA5"]) / row["MA5"] * 100, 1) < 3 if row["Close"] > row["MA5"] else False,
                axis=1
            )

            df["均線排列正確 且開口小"] = (
                (df["MA5"] >= df["MA10"]) &
                (df["MA10"] >= df["MA24"]) &
                (((df["MA5"] - df["MA10"]) / df["MA10"]) * 100 < 3)
            )

            df["帶量跌"] = (df["Volume"] > df["Volume"].shift(1)) & (df["Close"] < df["Close"].shift(1))

            # 判斷最後一筆是否符合 True, True, False
            last_row = df.tail(1).copy()
            if (
                last_row.iloc[0, -3] == True and
                last_row.iloc[0, -2] == True and
                last_row.iloc[0, -1] == False
            ):
                last_row.insert(0, "Stock", stock_code)
                all_report_rows.append(last_row)

        except Exception as e:
            print(f"❌ {stock_code} 處理失敗: {e}")

    # 輸出符合條件的總表
    if all_report_rows:
        report_df = pd.concat(all_report_rows, ignore_index=True)
        Path("output").mkdir(parents=True, exist_ok=True)
        report_df.to_csv("output/all_report.csv", index=False, encoding="utf-8-sig")
        print("📊 已輸出整併報告：output/all_report.csv")
