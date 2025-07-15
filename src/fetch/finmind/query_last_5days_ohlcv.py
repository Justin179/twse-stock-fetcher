from FinMind.data import DataLoader
from datetime import datetime, timedelta

def fetch_last_5_trading_days(stock_id: str):
    dl = DataLoader()

    # ✅ 登入 FinMind
    import os
    from dotenv import load_dotenv
    load_dotenv()
    user = os.getenv("FINMIND_USER_1")
    password = os.getenv("FINMIND_PASSWORD_1")
    if not dl.login(user_id=user, password=password):
        print("❌ FinMind 登入失敗")
        return

    # 抓最近 1 個月資料（取其中的最近 5 筆）
    today = datetime.today()
    start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    df = dl.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=start_date,
        end_date=end_date
    )

    if df.empty:
        print(f"❌ 查無 {stock_id} 的資料")
        return

    # 取最近 5 個交易日
    df = df.sort_values("date").tail(5)

    print(f"\n📈 {stock_id} 最近 5 個交易日 K 線資料:")
    print(df[["date", "open", "max", "min", "close", "Trading_Volume"]])

if __name__ == "__main__":
    # 可以自行改為其他股票代碼
    fetch_last_5_trading_days("3090")
