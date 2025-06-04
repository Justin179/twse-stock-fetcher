import zipfile
from pathlib import Path

def zip_project(output_name="my_stock_tools_full.zip"):
    root_dir = Path(__file__).parent.parent  # 專案根目錄
    output_dir = root_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_path = output_dir / output_name

    include_exts = [".py", ".txt", ".md", ".bat", ".gitignore"]
    include_dirs = ["src", "tools"]
    empty_dirs = ["data", "logs", "output"]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # 包含 src/, tools/ 中所有檔案
        for subdir in include_dirs:
            for path in (root_dir / subdir).rglob("*"):
                if path.is_file():
                    arcname = path.relative_to(root_dir)
                    zipf.write(path, arcname)

        # 包含根目錄的特定副檔名檔案
        for path in root_dir.glob("*"):
            if path.suffix in include_exts or path.name in include_exts:
                if path.is_file():
                    arcname = path.relative_to(root_dir)
                    zipf.write(path, arcname)

        # 保留空目錄
        for ed in empty_dirs:
            zippath = f"{ed}/"
            zipf.writestr(zippath, "")  # 寫入一個空目錄項目

    print(f"✅ 專案已打包到：{zip_path}")

if __name__ == "__main__":
    zip_project()