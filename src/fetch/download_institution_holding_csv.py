import httpx
import os

def download_twse_foreign_csv(date_str):
    """
    (暫時用不到)
    使用新版 TWSE RWD API 成功下載外資持股比率資料 csv
    存入 output/ 目錄
    """
    url = f"https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date={date_str}&selectType=ALLBUT0999&response=csv"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS"
    }

    try:
        with httpx.Client(verify=False, headers=headers, timeout=10.0, follow_redirects=True) as client:
            response = client.get(url)

        os.makedirs("output", exist_ok=True)

        if response.status_code == 200 and "證券代號" in response.text:
            filename = os.path.join("output", f"外資持股統計_{date_str}.csv")
            with open(filename, "w", encoding="utf-8-sig") as f:
                f.write(response.text)
            print(f"✅ 成功下載：{filename}")
        else:
            print("⚠️ 下載失敗，伺服器回應內容如下：")
            print(response.text[:300])

    except Exception as e:
        print(f"❌ 發生錯誤：{e}")

if __name__ == "__main__":
    download_twse_foreign_csv("20250529")  # ✅ 改成你要的日期
