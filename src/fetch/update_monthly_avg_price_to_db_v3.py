import sqlite3
from datetime import datetime
import httpx
import time

DB_PATH = "data/institution.db"

def get_missing_rows():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT stock_id, year_month
        FROM monthly_revenue
        WHERE monthly_avg_close IS NULL OR monthly_last_close IS NULL
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def fetch_avg_price(stock_id: str, year_month: str, max_retry: int = 3):
    date_str = datetime.strptime(year_month, "%Y%m").strftime("%Y%m01")
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY_AVG?response=json&date={date_str}&stockNo={stock_id}"

    for attempt in range(1, max_retry + 1):
        try:
            response = httpx.get(url, timeout=10.0, verify=False)
            data = response.json()
            rows = data.get("data", [])
            if not rows:
                print(f"[WARN] 第 {attempt} 次：{stock_id} {year_month} 沒有資料")
                time.sleep(1)
                continue

            avg_price = None
            last_day_price = None

            for i, row in enumerate(rows):
                if "月平均收盤價" in row[0]:
                    try:
                        avg_price = float(row[1].replace(",", ""))
                    except ValueError:
                        print(f"[WARN] {stock_id} {year_month} 月平均收盤價格式錯誤: {row[1]}")
                    if i > 0:
                        prev = rows[i - 1]
                        try:
                            last_day_price = float(prev[1].replace(",", ""))
                        except ValueError:
                            print(f"[WARN] {stock_id} {year_month} 月末收盤價格式錯誤: {prev[1]}")
                    break

            if avg_price is not None and last_day_price is not None:
                return avg_price, last_day_price
            else:
                print(f"[FAIL] {stock_id} {year_month} 欄位不完整")
                return None, None

        except Exception as e:
            print(f"[ERROR] 第 {attempt} 次：{stock_id} {year_month} 錯誤：{e}")
            time.sleep(1)

    print(f"[FAIL] 無法取得 {stock_id} {year_month}，經過 {max_retry} 次重試後仍失敗")
    return None, None

def update_price_to_db(stock_id: str, year_month: str, avg: float, last: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE monthly_revenue
        SET monthly_avg_close = ?, monthly_last_close = ?
        WHERE stock_id = ? AND year_month = ?
    """, (avg, last, stock_id, year_month))

    if cursor.rowcount > 0:
        print(f"[OK] 補上 {stock_id} {year_month} → avg: {avg}, last: {last}")
    else:
        print(f"[SKIP] 無資料可更新：{stock_id} {year_month}")

    conn.commit()
    conn.close()

def main():
    skip_stocks = {'2066', '3218', '5274', '6187', '6279', '8069', '8299', '8358'}
    missing_list = get_missing_rows()
    print(f"🔍 共需補上 {len(missing_list)} 筆資料")

    for stock_id, year_month in missing_list:
        if stock_id in skip_stocks:
            print(f"[SKIP] {stock_id} 為上櫃公司，跳過")
            continue

        avg, last = fetch_avg_price(stock_id, year_month)
        if avg and last:
            update_price_to_db(stock_id, year_month, avg, last)
        time.sleep(1)

if __name__ == "__main__":
    main()
