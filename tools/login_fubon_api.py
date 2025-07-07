# login_fubon_api.py

from fubon_neo.sdk import FubonSDK

import os
from dotenv import load_dotenv
load_dotenv()

user_id = os.getenv("FUBON_USER_ID")
password = os.getenv("FUBON_PASSWORD")
cert_path = os.getenv("FUBON_CERT_PATH")

def main():
    sdk = FubonSDK()
    accounts = sdk.login(user_id, password, cert_path) # 若憑證選用＂預設密碼＂, SDK v1.3.2與較新版本適用
    print("🔎 登入結果：", accounts)

    if accounts.is_success:
        print("✅ 登入成功！")
    else:
        print("❌ 登入失敗：", accounts.data)

    sdk.logout()

if __name__ == "__main__":
    main()
