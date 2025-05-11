import httpx
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from dateutil.relativedelta import relativedelta
from tqdm import tqdm


def get_twse_month_data(stock_code: str, date: datetime) -> list:
    date_str = date.strftime("%Y%m01")  # 固定為該月1號
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={stock_code}"
    # print(f"🔗 正在請求資料：{url}")  # 加這行就能印出 URL

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
    last_month = today.replace(day=1) - timedelta(days=1)
    # 抓本月、上個月、上上個月的資料
    this_month = today
    last_month = this_month.replace(day=1) - timedelta(days=1)
    two_months_ago = last_month.replace(day=1) - timedelta(days=1)

    all_data = []
    for date in [this_month, last_month, two_months_ago]:
        rows = get_twse_month_data(stock_code, date)
        all_data.extend(rows)

    df = convert_to_df(all_data)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    # ✅ 資料少於 10 筆就跳過儲存
    if len(df) < 10:
        return None

    # 儲存
    Path("data").mkdir(exist_ok=True)
    file_path = f"data/{stock_code}_history.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return df



def read_stock_list(file_path="stock_list.txt") -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

if __name__ == "__main__":
    for file in Path("data").glob("*_history.csv"):
        try:
            file.unlink()
        except:
            continue

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

