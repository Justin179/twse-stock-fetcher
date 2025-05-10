import pandas as pd
from pathlib import Path

# 讀取 all_report.csv（確保檔案存在於 output 目錄）
input_path = Path("output/all_report.csv")
df = pd.read_csv(input_path)

# 取出第一欄（預設是 "Stock"），並加上 .TW
xq_list = df.iloc[:, 0].astype(str) + ".TW"

# 匯出為 CSV，單欄垂直排列
output_path = Path("output/匯入XQ.csv")
xq_list.to_csv(output_path, index=False, header=False, encoding="utf-8-sig")

print(f"✅ 匯出完成：{output_path}")
