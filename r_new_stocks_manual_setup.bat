:: 當手上的持股庫存有新增的股票時，要先手動新增到 temp_list.txt，然後執行此腳本(建立初始資料)
:: 此腳本的用途是手動+指定更新特定股票，補上排程因時間差的缺失資料，裡面的py也可以單獨執行，缺啥補啥
@echo off
chcp 65001 > nul
cd /d %~dp0

:: 啟動虛擬環境（視實際情況修改）
call venv\Scripts\activate

:: 設定 log 檔案名稱（logs\20250617_log.txt）
if not exist logs (
    mkdir logs
)
set LOG_FILE=logs\%date:~0,4%%date:~5,2%%date:~8,2%_log.txt

echo ===== [09:30] 更新持倉 (回補 69 個月) ===== >> %LOG_FILE%
python src\fetch\finmind_db_fetcher.py temp_list.txt >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ===== [手動] 建立初始法人資料 (近99日) ===== >> %LOG_FILE%
python src\fetch\save_institutional_holding_multi.py >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ===== [10:00] 更新近5日法人資料 ===== >> %LOG_FILE%
python src\fetch\cmoney_institutional_multi_wz_schedule.py temp_list.txt >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ===== [10:07] 主力買賣超 & 買賣家數差 ===== >> %LOG_FILE%
python src\fetch\fetch_main_force_multi.py temp_list.txt >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ===== [8:00 & 22:14] 更新籌碼集中度與千張大戶比率 ===== >> %LOG_FILE%
python src\fetch\save_holder_concentration.py temp_list >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ===== [8:07 & 22:20] 更新月營收資料 ===== >> %LOG_FILE%
python src\fetch\fetch_monthly_revenue_multi_v5.py temp_list.txt >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ===== [8:12 & 10:25] 補齊月收盤與月均價 ===== >> %LOG_FILE%
python src\fetch\update_monthly_avg_price_from_local_db.py >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ===== [10:28] 更新三率(季報) ===== >> %LOG_FILE%
python src\fetch\fetch_profitability_histock.py temp_list.txt >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ===== [10:33] 季收盤價 ===== >> %LOG_FILE%
python src\fetch\update_season_close_price_from_local_db.py temp_list.txt >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo ✅ 所有任務完成，請查看 %LOG_FILE% >> %LOG_FILE%
echo ✅ 所有任務完成，請查看 %LOG_FILE%
pause
