# login_fubon_api.py

from fubon_neo.sdk import FubonSDK
import os
from dotenv import load_dotenv

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

def main():
    validate_env()
    
    sdk = FubonSDK()
    print("🚪 嘗試登入...")
    print(f"user_id: {user_id}")
    print(f"cert_path: {cert_path}")
    
    accounts = sdk.login(user_id, password, cert_path)
    print("📋 登入結果：", accounts)

    if accounts.is_success:
        print("✅ 登入成功！")
    else:
        print("❌ 登入失敗：")
        print("message:", accounts.message)
        print("data:", accounts.data)

    sdk.init_realtime()
    quote = sdk.marketdata.rest_client.stock.intraday.quote(symbol="2330")
    print("📈 即時報價：", quote)

    sdk.logout()

if __name__ == "__main__":
    main()
