import sqlite3
from pathlib import Path
import sys


def configure_console_encoding() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except ValueError:
            pass


configure_console_encoding()

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.ui.condition_selector import get_user_selected_conditions


# 價量同步+短多有撐開口小

conditions = {}

# ✅ 處理傳入參數（txt 檔案與 bias 閾值）
bias_threshold = 1.5
input_txt = None
for arg in sys.argv[1:]:
    if arg.lower().endswith(".txt"):
        input_txt = arg
    else:
        try:
            bias_threshold = float(arg)
        except ValueError:
            pass
if not input_txt:
    input_txt = "shareholding_concentration_list.txt"

def read_stock_list(file_path: str) -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        stock_list = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        # 去除重複的股票代碼，保持原順序
        return list(dict.fromkeys(stock_list))


input_name = Path(input_txt).stem.lower()
if input_name == "shareholding_concentration_list":
    xq_filename = "匯入XQ_籌碼集中度.csv"
elif input_name == "high_relative_strength_stocks":
    xq_filename = "匯入XQ_rs90強勢股.csv"
elif input_name == "break_above_last_months_high":
    xq_filename = "匯入XQ_過上月高點.csv"
else:
    xq_filename = f"{input_name}_output.csv"

def main() -> int:
    use_gui = True

    # 🎯 判斷是否為 high_relative_strength_stocks，套用自定義條件
    if input_name == "high_relative_strength_stocks":
        custom_conditions = {
            "收盤價站上 上彎5日均 且乖離小": True,
            "5 10多頭排列 均線上彎 開口小": True,
            "10 24多頭排列 均線上彎 開口小": True,
            "24日均乖離<15%": True,
            "量價同步": True,
            "收盤價站上上彎5週均": True,
            "站上上彎72日均": False
        }
    else:
        custom_conditions = None

    conditions = get_user_selected_conditions(
        use_gui=use_gui, default_conditions=custom_conditions, bias_threshold=bias_threshold)

    print("⏳ 載入分析模組中，請稍候...")
    import pandas as pd
    from src.analyze.stock_conditions import apply_conditions
    from src.analyze.calculate_weekly_ma import calculate_weekly_ma
    from src.common.db_helpers import fetch_stock_history_from_db

    db_path = str(Path(__file__).resolve().parent.parent / "data" / "institution.db")
    
    # 🔍 讀取原始股票清單並計算去重數量
    with open(input_txt, "r", encoding="utf-8") as f:
        original_stock_list = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    
    stock_list = read_stock_list(input_txt)
    duplicates_removed = len(original_stock_list) - len(stock_list)
    
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

                weekly_ma5 = calculate_weekly_ma(df, weeks=5)
                df["WMA5"] = df.index.map(weekly_ma5["WMA5"])


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
        f"\n📊 總覽：原始 {len(original_stock_list)} 檔，"
        f"去重 {duplicates_removed} 檔，"
        f"載入 {len(stock_list)} 檔，"
        f"遺失資料 {missing_data_count} 檔，"
        f"篩選排除 {filtered_out_count} 檔，"
        f"符合條件 {len(all_report_rows)} 檔"
    )

    if all_report_rows:
        report_df = pd.concat(all_report_rows, ignore_index=True)
        Path("output").mkdir(parents=True, exist_ok=True)
        report_df.to_csv("output/all_report.csv", index=False, encoding="utf-8-sig")

        xq_list = report_df["Stock"].astype(str) + ".TW"
        xq_path = Path("output") / xq_filename
        xq_list.to_csv(xq_path, index=False, header=False, encoding="utf-8-sig")

        print(
            f"📁 報表輸出：all_report.csv（{bias_threshold}%），"
            f"XQ 匯入：{xq_filename}（共 {len(xq_list)} 檔）\n"
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n⚠️ 偵測到使用者中斷執行，程式已停止。若畫面沒有跳出條件視窗，請先檢查它是否被其他視窗擋住。")
        raise SystemExit(130)
