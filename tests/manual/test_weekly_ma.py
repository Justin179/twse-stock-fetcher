import sqlite3
import pandas as pd
from pathlib import Path

# 匯入原始方法
from gen_filtered_report_db import fetch_stock_history_from_db, calculate_weekly_ma

if __name__ == "__main__":
    # 設定參數
    db_path = Path(__file__).resolve().parents[2] / "data" / "institution.db"
    print("DB path:", db_path)
    stock_code = "2317"  # ← 你可以改成任意股票代碼

    with sqlite3.connect(db_path) as conn:
        df = fetch_stock_history_from_db(conn, stock_code)

        if df.empty:
            print(f"❌ 無資料: {stock_code}")
        else:
            weekly_ma5 = calculate_weekly_ma(df, weeks=5)
            df["WMA5"] = df.index.map(weekly_ma5["WMA5"])

            print(df[["Close", "WMA5"]].tail(30))  # 印出最近30筆
