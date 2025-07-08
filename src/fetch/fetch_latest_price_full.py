# fetch_latest_price_full.py

import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv("FINMIND_TOKEN")

def fetch_latest_price_full(stock_id="2330"):
    if not TOKEN:
        print("❌ 請在 .env 檔案中設定 FINMIND_TOKEN")
        return

    url = "https://api.finmindtrade.com/api/v4/data"
    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }

    for i in range(0, 15):  # 最多往回查15天
        date = (datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d")
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": date
        }

        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        results = data.get("data", [])

        if results:
            latest = results[-1]
            print(f"📊 {stock_id} 最近資料（{latest['date']}）")
            print(f"    📈 開盤價：{latest['open']} 元")
            print(f"    🔼 最高價：{latest['max']} 元")
            print(f"    🔽 最低價：{latest['min']} 元")
            print(f"    🔚 收盤價：{latest['close']} 元")
            print(f"    📊 成交量：{latest['Trading_Volume']} 張")
            return

    print("❌ 無法在過去15日內找到任何資料")

if __name__ == "__main__":
    fetch_latest_price_full("2330")
