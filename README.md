# MyStockTools 程式說明

以下為專案中各 Python 檔案的用途與其內部函式概覽：

## `src/gen_filtered_report.py`
📌 主程式，讀取股票清單並根據條件套用過濾，產出符合條件的個股報表。

- **read_stock_list**: 讀取股票代碼清單

## `src/analyze/analyze_strong_days.py`
📌 分析個股近10日內的強勢天數，並可視覺化繪圖。

- **count_strong_days**: 該日是否強勢的定義
- **plot_strong_days**: 畫圖或視覺化資料
- **main**: 主流程入口

## `src/analyze/analyze_volume_price_relation.py`
📌 分析個股在近10日的價量同步與背離情況。

- **analyze_volume_price_relation**: 與檔案讀寫操作有關
- **get_relation**: 計算價量關係

## `src/analyze/stock_conditions.py`
📌 定義與套用各種選股條件，例如均線、乖離率、KD 等技術指標。

- **apply_conditions**: 處理或套用選股條件

## `src/fetch/twse_fetcher.py`
📌 從台灣證交所抓取個股每日成交資訊，依月份儲存歷史資料。

- **get_twse_month_data**: 抓證交所的資料(月份+股票代號)
- **convert_to_df**: 轉換資料格式
- **fetch_twse_history**: 下載或抓取資料
- **read_stock_list**: 讀取股票代碼清單

## `src/ui/condition_selector.py`
📌 提供 GUI 介面讓使用者互動選擇條件，回傳給主控程式使用。

- **get_user_selected_conditions**: 處理或套用選股條件
