import sys
import site
import pkg_resources
from pathlib import Path

def main():
    print("🔍 Python 執行環境資訊")
    print("-" * 40)

    print(f"✅ Python 版本：{sys.version.split()[0]}")
    print(f"✅ Python 執行路徑：{sys.executable}")
    print(f"✅ 虛擬環境路徑：{sys.prefix}")
    print(f"✅ site-packages 位置：{site.getsitepackages()[0]}")
    
    print("\n📦 已安裝的套件列表")
    print("-" * 40)
    installed = sorted([(d.project_name, d.version) for d in pkg_resources.working_set])
    for name, version in installed:
        print(f"{name:<30} {version}")

if __name__ == "__main__":
    main()
