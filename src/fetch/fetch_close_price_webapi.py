# fetch_close_price_webapi.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'tools')))

from login_helper import get_logged_in_sdk

def fetch_close_price(stock_id='2330'):
    sdk = get_logged_in_sdk()
    sdk.init_realtime()  # 初始化行情連線

    reststock = sdk.marketdata.rest_client.stock
    quote = reststock.intraday.quote(symbol=stock_id)

    close_price = quote.get("closePrice")
    print(f"📈 {stock_id} 最新成交價 closePrice：{close_price}")

    sdk.logout()

if __name__ == "__main__":
    fetch_close_price("2330")
