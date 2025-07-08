import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from common.login_helper import get_logged_in_sdk

def fetch_close_price(stock_id='2330'):
    sdk = get_logged_in_sdk()
    sdk.init_realtime()  # 初始化行情連線

    reststock = sdk.marketdata.rest_client.stock
    quote = reststock.intraday.quote(symbol=stock_id)

    # 基本行情資訊
    date = quote.get("date")
    close_price = quote.get("closePrice")
    open_price = quote.get("openPrice")
    high_price = quote.get("highPrice")
    low_price = quote.get("lowPrice")
    previous_close = quote.get("previousClose")
    trade_volume = quote.get("tradeVolume")

    print(f"📅 日期：{date}")
    print(f"📈 最新成交價 closePrice：{close_price}")
    print(f"🟢 開盤價 openPrice：{open_price}")
    print(f"🔺 最高價 highPrice：{high_price}")
    print(f"🔻 最低價 lowPrice：{low_price}")
    print(f"🔙 昨日收盤價 previousClose：{previous_close}")
    print(f"📊 累計成交量 tradeVolume：{trade_volume}")

    sdk.logout()

if __name__ == "__main__":
    fetch_close_price("3017")
