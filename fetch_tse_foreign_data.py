import requests
import pandas as pd
from datetime import datetime
import urllib3

# ✅ 停用 SSL 憑證警告（重要）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_tse_foreign_data(date_str: str):
    url = "https://www.twse.com.tw/fund/BFI82U"
    params = {
        "response": "json",
        "dayDate": date_str,
        "_": str(int(datetime.now().timestamp() * 1000))
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        # ✅ verify=False 允許略過 SSL 驗證
        response = requests.get(url, params=params, headers=headers, verify=False)
        data = response.json()

        if data["stat"] != "OK":
            print(f"{date_str} 無資料")
            return None

        df = pd.DataFrame(data["data"], columns=data["fields"])
        return df
    except Exception as e:
        print(f"{date_str} 抓取失敗: {e}")
        return None


# ✅ 測試執行
if __name__ == "__main__":
    date = "20250516"
    df = fetch_tse_foreign_data(date)
    if df is not None:
        df.to_csv(f"法人買賣超_{date}.csv", index=False, encoding="utf-8-sig")
        print(f"{date} 資料已儲存")
    else:
        print("未儲存")
