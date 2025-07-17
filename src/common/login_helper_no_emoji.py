# login_helper.py

from fubon_neo.sdk import FubonSDK
import os
from dotenv import load_dotenv

# 強制載入 .env 設定
load_dotenv(override=True)

def get_logged_in_sdk():
    user_id = os.getenv("FUBON_USER_ID")
    password = os.getenv("FUBON_PASSWORD")
    cert_path = os.getenv("FUBON_CERT_PATH")

    # 驗證環境變數與檔案存在
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
        for err in errors:
            print("錯誤:", err)
        raise EnvironmentError("登入資訊錯誤，請檢查 .env 與憑證檔案")

    sdk = FubonSDK()
    print("嘗試登入富邦 API...")
    result = sdk.login(user_id, password, cert_path)

    if not result.is_success:
        print("登入失敗：", result.message)
        raise ConnectionError("富邦 API 登入失敗")

    print("登入成功")
    return sdk
