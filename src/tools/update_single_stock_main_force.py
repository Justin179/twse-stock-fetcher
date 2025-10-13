"""
背景執行：更新單一股票的主力買賣超資料
使用方式: python src/tools/update_single_stock_main_force.py <stock_id>
"""
import sys
import os

# 添加專案根目錄到 Python 路徑
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from src.fetch.fetch_main_force_multi import fetch_main_force, save_to_db as save_cmoney_to_db
from src.fetch.fetch_wantgoo_main_trend import fetch_wantgoo_main_trend, save_to_db as save_wantgoo_to_db


def main():
    if len(sys.argv) < 2:
        print("❌ 請提供股票代碼")
        sys.exit(1)
    
    stock_id = sys.argv[1]
    print(f"開始更新 {stock_id} 主力買賣超資料...")
    
    total_inserted = 0
    
    # 1. 更新 CMoney 主力進出資料
    try:
        print(f"📥 [CMoney] 抓取 {stock_id}...")
        records_cmoney = fetch_main_force(stock_id)
        if records_cmoney:
            inserted = save_cmoney_to_db(records_cmoney)
            total_inserted += inserted
            print(f"✅ [CMoney] 新增 {inserted} 筆")
        else:
            print(f"⏭️  [CMoney] 無新資料")
    except Exception as e:
        print(f"❌ [CMoney] 錯誤: {e}")
    
    # 2. 更新 WantGoo 主力進出資料
    try:
        print(f"📥 [WantGoo] 抓取 {stock_id}...")
        records_wantgoo = fetch_wantgoo_main_trend(stock_id)
        if records_wantgoo:
            inserted = save_wantgoo_to_db(records_wantgoo)
            total_inserted += inserted
            print(f"✅ [WantGoo] 新增 {inserted} 筆")
        else:
            print(f"⏭️  [WantGoo] 無新資料")
    except Exception as e:
        print(f"❌ [WantGoo] 錯誤: {e}")
    
    # 3. 完成提示
    if total_inserted > 0:
        print(f"\n✅ {stock_id} 更新完成！共新增 {total_inserted} 筆資料")
    else:
        print(f"\n⚠️ {stock_id} 無新資料")
    
    # 播放提示音
    try:
        import subprocess
        subprocess.run([
            'powershell', '-Command',
            "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\Windows Logon.wav').PlaySync()"
        ], check=False)
    except:
        pass


if __name__ == "__main__":
    main()
