import sqlite3
import pandas as pd
from pathlib import Path

# 匯入原始方法
from gen_filtered_report_db import fetch_stock_history_from_db
from analyze.calculate_weekly_ma import calculate_weekly_ma

if __name__ == "__main__":
    # 設定參數
    db_path = Path(__file__).resolve().parents[2] / "data" / "institution.db"
    print("DB path:", db_path)
    stock_code = "2891"  # ← 你可以改成任意股票代碼 2317

    with sqlite3.connect(db_path) as conn:
        df = fetch_stock_history_from_db(conn, stock_code)

        if df.empty:
            print(f"❌ 無資料: {stock_code}")
        else:
            weekly_ma5 = calculate_weekly_ma(df, weeks=5)
            df["WMA5"] = df.index.map(weekly_ma5["WMA5"])

            # 從每週最後交易日的 WMA5 中取最近6筆
            wma_series = df["WMA5"].dropna().drop_duplicates().tail(6)
            is_upward = wma_series.iloc[-1] > wma_series.iloc[0]
            print(wma_series.iloc[-1])
            print(wma_series.iloc[0])
            print(is_upward)


            # print(df[["Close", "WMA5"]].tail(30))  # 印出最近30筆

            # df["收盤價站上5週均"] = df.iloc[-1]["Close"] > df.iloc[-1]["WMA5"]

            
            週收盤價 = df.iloc[-1]["Close"]
            五週均線 = df.iloc[-1]["WMA5"]
            

            # print(df.iloc[-1]["Close"])
            # print(df.iloc[-1]["WMA5"])
            # print(df.iloc[-6]["Close"])
            # print("收盤價站上5週均1:", df.iloc[-1]["收盤價站上5週均"])
            # print("收盤價站上5週均2:", df["收盤價站上5週均"])
