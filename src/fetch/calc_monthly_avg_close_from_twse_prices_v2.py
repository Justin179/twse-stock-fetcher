import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "data/institution.db"
STOCK_ID = "2066"  # ✅ 修改這裡可以換個股

def main():
    # 連線並讀取該股每日收盤價
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT date, close
        FROM twse_prices
        WHERE stock_id = '{STOCK_ID}'
        ORDER BY date
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print(f"⚠️ 查無個股 {STOCK_ID} 的資料")
        return

    # 將 date 欄轉換為 datetime，失敗的設為 NaT，並移除
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # 加入年月欄位
    df["year_month"] = df["date"].dt.strftime("%Y%m")

    # 分組計算：月均收盤 + 當月最後收盤
    result = df.groupby("year_month").agg(
        monthly_avg_close=("close", "mean"),
        monthly_last_close=("close", lambda x: x.iloc[-1])
    ).reset_index()

    # 四捨五入取兩位小數
    result["monthly_avg_close"] = result["monthly_avg_close"].round(2)
    result["monthly_last_close"] = result["monthly_last_close"].round(2)

    # 顯示結果
    print(result)

    # 可選：匯出 CSV
    Path("output").mkdir(exist_ok=True)
    result.to_csv(f"output/monthly_price_summary_{STOCK_ID}.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 已匯出至 output/monthly_price_summary_{STOCK_ID}.csv")

if __name__ == "__main__":
    main()
