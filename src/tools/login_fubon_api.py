# login_fubon_api.py

from fubon_neo.sdk import FubonSDK
import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
import argparse

# 強制覆蓋舊的環境變數
load_dotenv(override=True)

user_id = os.getenv("FUBON_USER_ID")
password = os.getenv("FUBON_PASSWORD")
cert_path = os.getenv("FUBON_CERT_PATH")

def validate_env():
    print("🔍 驗證登入資訊...")
    errors = []
    
    if not user_id:
        errors.append("FUBON_USER_ID 缺少")
    if not password:
        errors.append("FUBON_PASSWORD 缺少")
    if not cert_path:
        errors.append("FUBON_CERT_PATH 缺少")
    elif not os.path.exists(cert_path):
        errors.append(f"憑證檔案不存在：{cert_path}")

    if errors:
        print("❌ 錯誤：")
        for err in errors:
            print("  -", err)
        exit(1)
    else:
        print("✅ 所有登入資訊都正確")

# 直接搬過來測試的函式 from fetch_fubon_daily_ohlcv_all_stocks_wz_auto_log.py
def fetch_daily_ohlcv(sdk, symbol, days=10):
    end = datetime.today()
    start = end - pd.Timedelta(days=days * 2)
    sdk.init_realtime()
    reststock = sdk.marketdata.rest_client.stock
    try:
        result = reststock.historical.candles(
            symbol=symbol,
            from_=start.strftime("%Y-%m-%d"),
            to=end.strftime("%Y-%m-%d"),
            timeframe="D"
        )
        return pd.DataFrame(result.get("data", []))
    except Exception as e:
        print(f"{symbol} 抓取失敗: {e}")
        return None

def fetch_intraday_quote(sdk, symbol):
    try:
        sdk.init_realtime()
        quote = sdk.marketdata.rest_client.stock.intraday.quote(symbol=symbol)
        print("📦 原始即時報價 JSON：", quote)

        vol = (quote.get("total") or {}).get("tradeVolume")
        if vol is None:
            vol = quote.get("volume")  # 備援

        out = {
            "date": quote.get("date"),                 # 'YYYY-MM-DD'
            "o":    quote.get("openPrice"),
            "h":    quote.get("highPrice"),
            "l":    quote.get("lowPrice"),
            "c1":   quote.get("closePrice"),
            "c2":   quote.get("previousClose"),
            "v":    vol,                                # ← 正確位置
            "symbol": quote.get("symbol"),
            "name": quote.get("name"),
        }

        print(
            f"🧾 {out.get('symbol')} {out.get('name','')} "
            f"date={out['date']}, O={out['o']}, H={out['h']}, L={out['l']}, "
            f"C1={out['c1']}, C2(昨)={out['c2']}, V={out['v']}"
        )
        return out
    except Exception as e:
        print(f"❌ 抓取即時報價失敗 {symbol}: {e}")
        return None


def main():
    # 允許從命令列指定股票，預設 2330
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="2330", help="股票代碼（預設：2330）")
    ap.add_argument("--days", type=int, default=10, help="歷史日K抓取天數（預設：10）")
    args = ap.parse_args()

    validate_env()
    
    sdk = FubonSDK()
    print("🚪 嘗試登入...")
    accounts = sdk.login(user_id, password, cert_path)
    print("📋 登入結果：", accounts)

    if accounts.is_success:
        print("✅ 登入成功！")
    else:
        print("❌ 登入失敗：")
        print("message:", accounts.message)
        print("data:", accounts.data)
        return

    # 呼叫 fetch_daily_ohlcv 抓取歷史報價，看跟db是否一致 (是的，db的volume的資料源是從fubon抓的)
    df = fetch_daily_ohlcv(sdk, args.symbol, days=args.days)
    print(f"📈 {args.symbol} 最近日K：")
    print(df)

    # 呼叫 intraday/quote 抓「盤中 O/H/L/C/V」
    print("\n⏱️ 嘗試取得盤中即時 O/H/L/C/V ...")
    out = fetch_intraday_quote(sdk, args.symbol)

    sdk.logout()
    print("👋 已登出。")

if __name__ == "__main__":
    main()
