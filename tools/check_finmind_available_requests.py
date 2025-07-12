
from dotenv import load_dotenv
import os
from FinMind.data import DataLoader

def check_available_requests(index):
    load_dotenv()
    user = os.getenv(f"FINMIND_USER_{index}")
    password = os.getenv(f"FINMIND_PASSWORD_{index}")
    token = os.getenv(f"FINMIND_TOKEN_{index}")

    if not user or not password:
        print(f"❌ 帳號 {index} 未設定，跳過")
        return

    dl = DataLoader()
    if not dl.login(user_id=user, password=password):
        print(f"❌ 帳號 {index} 登入失敗")
        return
    if token:
        dl.token = token

    try:
        _ = dl.taiwan_stock_info()
        available = dl.api_usage_limit - dl.api_usage
        print(f"✅ 帳號 {index} ({user}) 可用 request 數：{available}")
    except Exception as e:
        print(f"⚠️ 帳號 {index} ({user}) 取得失敗：{e}")

def main():
    for i in range(1, 4):
        check_available_requests(i)

if __name__ == "__main__":
    main()
