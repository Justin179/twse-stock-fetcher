import httpx
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from dateutil.relativedelta import relativedelta
from tqdm import tqdm

def get_twse_month_data(stock_code: str, date: datetime) -> list:
    date_str = date.strftime("%Y%m01")  # 固定為該月1號
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={stock_code}"
    # print(f"🔗 正在請求資料：{url}")

    try:
        response = httpx.get(url, timeout=10.0, verify=False)
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        return []

def convert_to_df(data_rows: list) -> pd.DataFrame:
    records = []
    for row in data_rows:
        try:
            roc_date = row[0].replace("/", "-")
            y, m, d = map(int, roc_date.split("-"))
            date = datetime(y + 1911, m, d).strftime("%Y-%m-%d")
            open_ = float(row[3].replace(",", ""))
            high = float(row[4].replace(",", ""))
            low = float(row[5].replace(",", ""))
            close = float(row[6].replace(",", ""))
            volume = int(row[1].replace(",", ""))
            records.append([date, open_, high, low, close, volume])
        except:
            continue
    return pd.DataFrame(records, columns=["Date", "Open", "High", "Low", "Close", "Volume"])

def fetch_twse_history(stock_code: str):
    today = datetime.today()
    file_path = Path(f"data/{stock_code}_history.csv")
    Path("data").mkdir(exist_ok=True)

    # ✅ 若已有歷史檔，先載入並找出最後一天日期
    if file_path.exists():
        try:
            existing_df = pd.read_csv(file_path, parse_dates=["Date"])
            last_date = existing_df["Date"].max()
        except Exception as e:
            print(f"❌ 無法讀取舊檔 {stock_code}: {e}")
            return None
    else:
        existing_df = pd.DataFrame()
        last_date = today - relativedelta(months=12)

    all_data = []
    failed_months = []

    for i in range(12):
        date = today - relativedelta(months=i)
        # 若該月份資料日期小於等於最後一天，跳過
        if date < last_date.replace(day=1):
            continue
        rows = get_twse_month_data(stock_code, date)
        df_month = convert_to_df(rows)
        if df_month.empty:
            failed_months.append(date.strftime('%Y-%m'))
        else:
            all_data.extend(rows)

    if failed_months:
        print(f"⚠️ {stock_code} 缺少月份資料：{', '.join(failed_months)}，已跳過")
        return None

    df_new = convert_to_df(all_data)
    if not df_new.empty:
        df_new["Date"] = pd.to_datetime(df_new["Date"])
        if not existing_df.empty:
            df = pd.concat([existing_df, df_new], ignore_index=True)
            df = df.drop_duplicates(subset="Date")
        else:
            df = df_new
        df = df.sort_values("Date").reset_index(drop=True)
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        return df
    else:
        return existing_df if not existing_df.empty else None

def read_stock_list(file_path="stock_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

if __name__ == "__main__":
    stock_list = read_stock_list("stock_list.txt")

    success_count = 0
    skip_count = 0

    print(f"📦 開始抓取 TWSE 歷史資料（共 {len(stock_list)} 檔）...")

    for stock_code in tqdm(stock_list, desc="處理中", ncols=80):
        df = fetch_twse_history(stock_code)
        if df is None:
            skip_count += 1
        else:
            success_count += 1

    print("\n📊 抓取完畢")
    print(f"✅ 成功儲存：{success_count} 檔")
    print(f"⚠️ 資料不足未產出：{skip_count} 檔")
    print()  # 空一行
