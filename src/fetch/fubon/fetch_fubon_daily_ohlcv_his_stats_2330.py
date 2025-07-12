import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))
from common.login_helper import get_logged_in_sdk
from datetime import datetime, timedelta
import pandas as pd

# Historical Stats
# 取得近 52 週股價數據（依代碼查詢）
# https://www.fbs.com.tw/TradeAPI/docs/market-data/http-api/historical/stats
# 歷史行情 : 60 / min (如果您 API 請求超過了限制，將收到帶有狀態碼 429 的回應。需再等候1分鐘。)
'''
有點沒用…
{'date': '2025-07-11', 'type': 'EQUITY', 'exchange': 'TWSE', 'market': 'TSE', 'symbol': '2330', 
'name': '台積電', 'openPrice': 1095, 'highPrice': 1100, 'lowPrice': 1090, 'closePrice': 1100, 'change': 0, 
'tradeVolume': 30615792, 'tradeValue': 33607768195, 'previousClose': 1100, 'week52High': 1160, 'week52Low': 780}
'''

def fetch_daily_ohlcv(sdk, symbol="2330", days=10):
    sdk.init_realtime()  # 初始化 SDK
    reststock = sdk.marketdata.rest_client.stock

    result = reststock.historical.stats(symbol=symbol)
    print(result)

    data = result.get("data", [])
    if not data:
        print("❌ 查詢失敗或無資料")
        return None

    df = pd.DataFrame(data)
    print(df)
    return df


def main():
    sdk = get_logged_in_sdk()
    df = fetch_daily_ohlcv(sdk, symbol="2330", days=10)
    # if df is not None:
    #     print(df.tail())

if __name__ == "__main__":
    main()
