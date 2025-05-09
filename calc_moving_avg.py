import pandas as pd
from pathlib import Path

def calculate_moving_averages(input_file: str, stock_code: str, output_dir: str = "."):
    """
    讀取股價CSV檔，計算最後5個交易日的5日、10日、24日均價，並輸出成新CSV檔。

    Args:
        input_file (str): 原始股價CSV檔案路徑
        stock_code (str): 股票代碼
        output_dir (str): 輸出檔案存放目錄（預設為目前目錄）
    """
    input_path = Path(input_file)
    output_path = Path(output_dir) / f"{stock_code}_均價.csv"

    # 讀取CSV資料
    df = pd.read_csv(input_path, index_col=0, parse_dates=True)

    # 計算均價（以收盤價為基礎）
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA10"] = df["Close"].rolling(window=10).mean()
    df["MA24"] = df["Close"].rolling(window=24).mean()
    df[["MA5", "MA10", "MA24"]] = df[["MA5", "MA10", "MA24"]].round(1)
    df["Volume"] = (df["Volume"] / 1000).round().astype(int)


    # 取出最後5筆資料
    result = df[["Close", "MA5", "MA10", "MA24","Volume"]].tail(5)

    # 輸出成CSV
    result.to_csv(output_path, encoding="utf-8-sig")
    print(f"✅ 已輸出到：{output_path}")


def filter_n_gen_report(input_file: str, stock_code: str, output_dir: str = "output") -> None:
    # 讀取資料
    df = pd.read_csv(input_file)

    # 加入一欄：判斷收盤價是否高於 MA5
    # df["Above_MA5"] = df["Close"] >= df["MA5"]

    # 判斷：收盤價高於 MA5 且 乖離率 < 3%（保留 1 位小數再比較）
    df["站上5日均 且乖離小"] = df.apply(
        lambda row: round((row["Close"] - row["MA5"]) / row["MA5"] * 100, 1) < 3 if row["Close"] > row["MA5"] else False,
        axis=1
    )

    # 判斷均線排列是否正確 (MA5 >= MA10 且 MA10 >= MA24)
    # df["MA_order_correct"] = (df["MA5"] >= df["MA10"]) & (df["MA10"] >= df["MA24"])

    # 計算 MA5 相對 MA10 的乖離率（保留 1 位小數）
    # df["Bias_MA5_MA10"] = round((df["MA5"] - df["MA10"]) / df["MA10"] * 100, 1)

    # 判斷均線排列正確 且 乖離率 < 3%
    df["均線排列正確 且開口小"] = (
        (df["MA5"] >= df["MA10"]) &
        (df["MA10"] >= df["MA24"]) &
        (((df["MA5"] - df["MA10"]) / df["MA10"]) * 100 < 3)
    )


    # 判斷是否量增下跌（成交量大於前一日且收盤價低於前一日）
    df["帶量跌"] = (df["Volume"] > df["Volume"].shift(1)) & (df["Close"] < df["Close"].shift(1))



    # 確保輸出資料夾存在
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 輸出結果
    output_path = Path(output_dir) / f"{stock_code}_report.csv"
    df.to_csv(output_path, encoding="utf-8-sig", index=False)

    print(f"✅ 分析完成，已儲存至：{output_path}")


# 範例執行
if __name__ == "__main__":
    calculate_moving_averages("data/2330_history.csv", "2330", "data")
    filter_n_gen_report("data/2330_均價.csv", "2330", "output")
