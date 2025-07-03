import pandas as pd
import sqlite3
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.analyze.stock_conditions import apply_conditions
from src.ui.condition_selector import get_user_selected_conditions

use_gui = True  # 或 False for CLI/排程
conditions = get_user_selected_conditions(use_gui=use_gui)
bias_threshold = float(sys.argv[1]) if len(sys.argv) > 1 else 2

def read_stock_list(file_path="shareholding_concentration_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def fetch_stock_history_from_db(conn, stock_code: str) -> pd.DataFrame:
    query = '''
        SELECT date, close AS Close, volume AS Volume
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date
    '''
    df = pd.read_sql_query(query, conn, params=(stock_code,))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df

if __name__ == "__main__":
    db_path = str(Path(__file__).resolve().parent.parent / "data" / "institution.db")
    stock_list = read_stock_list("shareholding_concentration_list.txt")
    all_report_rows = []
    missing_data_count = 0
    filtered_out_count = 0

    with sqlite3.connect(db_path) as conn:
        for stock_code in stock_list:
            try:
                print(f"\n🔍 正在處理 {stock_code}...")
                df = fetch_stock_history_from_db(conn, stock_code)

                if df.empty or len(df) < 200:
                    print(f"⚠️ {stock_code} 資料不足（筆數：{len(df)}）")
                    missing_data_count += 1
                    continue

                df["MA5"] = df["Close"].rolling(window=5).mean()
                df["MA10"] = df["Close"].rolling(window=10).mean()
                df["MA24"] = df["Close"].rolling(window=24).mean()
                df["MA72"] = df["Close"].rolling(window=72).mean()
                df["MA200"] = df["Close"].rolling(window=200).mean()
                df[["MA5", "MA10", "MA24", "MA72", "MA200"]] = df[["MA5", "MA10", "MA24", "MA72", "MA200"]].round(2)
                df["Volume"] = (df["Volume"] / 1000).round().astype(int)

                if df["MA5"].isnull().all():
                    print(f"⚠️ {stock_code} 所有 MA5 均為 NaN，無法進行條件判斷")

                df = apply_conditions(df, bias_threshold)

                last_row = df.tail(1).copy()
                if all(last_row[col].iloc[0] == True for col, expected in conditions.items() if expected is True):
                    last_row.insert(0, "Stock", stock_code)
                    all_report_rows.append(last_row)
                else:
                    filtered_out_count += 1

            except Exception as e:
                print(f"❌ {stock_code} 處理失敗: {e}")

    print(
        f"\n📊 總覽：載入 {len(stock_list)} 檔，"
        f"遺失資料 {missing_data_count} 檔，"
        f"篩選排除 {filtered_out_count} 檔，"
        f"符合條件 {len(all_report_rows)} 檔"
    )

    if all_report_rows:
        report_df = pd.concat(all_report_rows, ignore_index=True)
        Path("output").mkdir(parents=True, exist_ok=True)
        report_df.to_csv("output/all_report.csv", index=False, encoding="utf-8-sig")

        xq_list = report_df["Stock"].astype(str) + ".TW"
        xq_path = Path("output") / "匯入XQ.csv"
        xq_list.to_csv(xq_path, index=False, header=False, encoding="utf-8-sig")

        print(
            f"📁 報表輸出：all_report.csv（{bias_threshold}%），"
            f"XQ 匯入：匯入XQ.csv（共 {len(xq_list)} 檔）\n"
        )
