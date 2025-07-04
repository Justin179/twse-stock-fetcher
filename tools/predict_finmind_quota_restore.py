import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from FinMind.data import DataLoader

LOG_DIR = "logs"
THRESHOLD = 500  # 預期恢復到多少 quota 為目標

def parse_log_timestamps(log_path):
    timestamps = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if "Request #" in line:
                # 格式: 2025-07-04 07:40:12,244 [INFO] Request #123: 2330
                match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if match:
                    ts = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                    timestamps.append(ts)
    return timestamps

def predict_restore_time(request_times, current_quota):
    if current_quota >= THRESHOLD:
        print(f"✅ 目前 request quota 已達 {current_quota}，無需等待。")
        return

    needed_to_release = THRESHOLD - current_quota
    if len(request_times) < needed_to_release:
        print("❌ log 中的 request 符合數不足，無法推估恢復時間")
        return

    # 取出第 N 筆 request 時間，推估其在 60 分鐘後會釋放
    target_ts = request_times[needed_to_release - 1]
    restore_ts = target_ts + timedelta(hours=1)
    print(f"⏳ 預估約在 {restore_ts.strftime('%H:%M:%S')} quota 將恢復至 {THRESHOLD}+")

def main():
    load_dotenv()
    user = os.getenv("FINMIND_USER")
    password = os.getenv("FINMIND_PASSWORD")
    dl = DataLoader()
    if not dl.login(user_id=user, password=password):
        print("❌ 登入 FinMind 失敗")
        return

    current_quota = dl.api_usage_limit
    print(f"📊 FinMind 剩餘 quota：{current_quota}")

    today_str = datetime.today().strftime("%Y%m%d")
    log_path = os.path.join(LOG_DIR, f"finmind_{today_str}.txt")

    if not os.path.exists(log_path):
        print(f"❌ 找不到當日 log 檔：{log_path}")
        return

    timestamps = parse_log_timestamps(log_path)
    predict_restore_time(timestamps, current_quota)

if __name__ == "__main__":
    main()
