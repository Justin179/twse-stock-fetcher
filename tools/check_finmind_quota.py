import os
from dotenv import load_dotenv
from FinMind.data import DataLoader

def main():
    # 載入 .env 檔
    load_dotenv()
    user = os.getenv("FINMIND_USER")
    password = os.getenv("FINMIND_PASSWORD")

    # 登入 FinMind
    dl = DataLoader()
    success = dl.login(user_id=user, password=password)
    if not success:
        print("❌ FinMind 登入失敗")
        return

    # 顯示剩餘 request 數
    quota = dl.api_usage_limit
    print(f"📊 FinMind 剩餘可用 request 數：{quota}")

if __name__ == "__main__":
    main()
