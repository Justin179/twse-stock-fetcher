import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))
from common.login_helper import get_logged_in_sdk
from datetime import datetime, timedelta
import pandas as pd

# Candles
# https://www.fbs.com.tw/TradeAPI/docs/market-data/http-api/historical/candles
# 歷史行情 : 60 / min (如果您 API 請求超過了限制，將收到帶有狀態碼 429 的回應。需再等候1分鐘。)

def fetch_daily_ohlcv(sdk, symbol="2330", days=10):
    end = datetime.today()
    start = end - timedelta(days=days * 2)  # 考慮非交易日

    sdk.init_realtime()  # 初始化 SDK
    reststock = sdk.marketdata.rest_client.stock

    result = reststock.historical.candles(
        symbol=symbol,
        from_=start.strftime("%Y-%m-%d"),
        to=end.strftime("%Y-%m-%d"),
        timeframe="D"
    ) # 週k(W) 月k(M) 日k(D)
    print(start.strftime("%Y-%m-%d"))  # 輸出起始日期

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
