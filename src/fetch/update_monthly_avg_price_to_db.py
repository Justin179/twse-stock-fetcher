import sqlite3
import httpx
from datetime import datetime

def fetch_avg_price(stock_id: str, year_month: str):
    date_str = datetime.strptime(year_month, "%Y%m").strftime("%Y%m01")
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY_AVG?response=json&date={date_str}&stockNo={stock_id}"

    try:
        response = httpx.get(url, timeout=10.0, verify=False)  # ✅ 關閉 SSL 驗證
        data = response.json()

        if not data.get("data"):
            print(f"[WARN] {stock_id} {year_month} 沒有資料")
            return None, None

        last_day_price = None
        avg_price = None
        for item in data["data"]:
            if "月平均收盤價" in item[0]:
                avg_price = float(item[1].replace(",", ""))
            elif "/" in item[0]:
                last_day_price = float(item[1].replace(",", ""))
        
        return avg_price, last_day_price

    except Exception as e:
        print(f"[ERROR] 無法取得 {stock_id} {year_month} 資料: {e}")
        return None, None

def update_db(stock_id: str, year_month: str, avg_price: float, last_price: float, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE monthly_revenue ADD COLUMN monthly_avg_close REAL;")
    except sqlite3.OperationalError:
        pass  # 已存在

    try:
        cursor.execute("ALTER TABLE monthly_revenue ADD COLUMN monthly_last_close REAL;")
    except sqlite3.OperationalError:
        pass  # 已存在

    cursor.execute("""
        UPDATE monthly_revenue
        SET monthly_avg_close = ?, monthly_last_close = ?
        WHERE stock_id = ? AND year_month = ?
    """, (avg_price, last_price, stock_id, year_month))

    if cursor.rowcount == 0:
        print(f"[INFO] 無對應資料可更新：{stock_id} {year_month}")
    else:
        print(f"[OK] 已更新：{stock_id} {year_month} → avg: {avg_price}, last: {last_price}")

    conn.commit()
    conn.close()

def main():
    stock_id = "2330"
    year_month = "202505"
    avg_price, last_price = fetch_avg_price(stock_id, year_month)
    if avg_price and last_price:
        update_db(stock_id, year_month, avg_price, last_price)

if __name__ == "__main__":
    main()
