from pathlib import Path
import shutil

base = Path(".")  # 👉 原地整理（不建立 Refactored 資料夾）

# 建立整理用的子資料夾
folders = ["src/analyze", "src/fetch", "src/ui", "tools", "backup_py"]
for folder in folders:
    (base / folder).mkdir(parents=True, exist_ok=True)

# 備份 + 移動 的檔案清單與對應目的地
move_map = {
    "gen_filtered_report.py": "src/gen_filtered_report.py",
    "stock_conditions.py": "src/analyze/stock_conditions.py",
    "twse_fetcher.py": "src/fetch/twse_fetcher.py",
    "fetch_tse_foreign_data.py": "src/fetch/fetch_tse_foreign_data.py",
    "condition_selector.py": "src/ui/condition_selector.py",
    "check_venv.py": "tools/check_venv.py",
    "zip_my_project.py": "tools/zip_my_project.py",
}

for filename, dest in move_map.items():
    src_path = base / filename
    dst_path = base / dest
    backup_path = base / "backup_py" / filename

    if src_path.exists():
        shutil.copy2(src_path, backup_path)   # ✅ 備份
        shutil.move(src_path, dst_path)       # ✅ 移動
        print(f"✅ 已移動 {filename} → {dest}，並備份至 backup_py/")
    else:
        print(f"⚠️ 找不到 {filename}，跳過")

print("\n🎉 原地整理與備份完成！")
