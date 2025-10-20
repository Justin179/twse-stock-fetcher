"""
T+2 交易在途應收付追蹤器
追蹤台股 T+2 制度下的在途應收付金額，計算真實帳戶餘額
"""

import streamlit as st
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

# 資料檔案路徑
DATA_FILE = Path(__file__).parent.parent.parent / "data" / "t2_settlement.json"
DB_PATH = Path(__file__).parent.parent.parent / "data" / "institution.db"

def get_latest_trading_date():
    """從 twse_prices 取得最新交易日（使用台積電 2330）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = """
        SELECT date 
        FROM twse_prices 
        WHERE stock_id = '2330' 
        ORDER BY date DESC 
        LIMIT 1
        """
        
        cursor.execute(query)
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]  # 返回日期字串，例如 '2025-10-14'
        else:
            return None
    except Exception as e:
        st.error(f"查詢最新交易日時發生錯誤: {e}")
        return None

def get_trading_days_diff(date1, date2):
    """
    計算兩個日期之間的交易日差異（使用台積電 2330 的交易記錄）
    
    Args:
        date1: 較早的日期 (str, 格式: 'YYYY-MM-DD')
        date2: 較晚的日期 (str, 格式: 'YYYY-MM-DD')
    
    Returns:
        int: 交易日差異（date2 比 date1 晚幾個交易日）
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 查詢 date1 和 date2 之間的所有交易日（包含 date1，不包含 date2）
        query = """
        SELECT COUNT(*) 
        FROM twse_prices 
        WHERE stock_id = '2330' 
        AND date > ? 
        AND date <= ?
        """
        
        cursor.execute(query, (date1, date2))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        else:
            return 0
    except Exception as e:
        st.error(f"查詢交易日差異時發生錯誤: {e}")
        return 0

def load_settlement_data():
    """載入在途應收付資料"""
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_settlement_data(data):
    """儲存在途應收付資料（只保留最近3筆）"""
    # 確保目錄存在
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 按日期排序，只保留最近3筆
    sorted_dates = sorted(data.keys(), reverse=True)[:3]
    filtered_data = {date: data[date] for date in sorted_dates}
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, ensure_ascii=False, indent=2)

def get_previous_trading_date(reference_date):
    """
    從資料庫查詢指定日期的上一個交易日
    
    Args:
        reference_date: 參考日期 (str, 格式: 'YYYY-MM-DD')
    
    Returns:
        str: 上一個交易日的日期，如果沒有則返回 None
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = """
        SELECT date 
        FROM twse_prices 
        WHERE stock_id = '2330' 
        AND date < ?
        ORDER BY date DESC 
        LIMIT 1
        """
        
        cursor.execute(query, (reference_date,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        else:
            return None
    except Exception as e:
        st.error(f"查詢上一個交易日時發生錯誤: {e}")
        return None

def get_pending_amount(latest_trading_date):
    """
    取得在途應收付金額（上一個交易日的金額）
    
    邏輯說明：
    情況 A（通常）：資料庫最新交易日 < 今天
        - 最新交易日就是「上一個交易日」
        - 例如：今天 10-20，最新交易日 10-17 → 在途金額 = 10-17
    
    情況 B（傍晚後）：資料庫最新交易日 = 今天
        - 需要往前找一個交易日
        - 例如：今天 10-20，最新交易日 10-20 → 往前找 → 在途金額 = 10-17
    """
    data = load_settlement_data()
    
    if not data:
        return 0, None
    
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # 判斷最新交易日是否等於今天
    if latest_trading_date == today_date:
        # 情況 B：資料庫已更新今天的資料，往前找上一個交易日
        previous_date = get_previous_trading_date(latest_trading_date)
        if previous_date and previous_date in data:
            return data[previous_date], previous_date
    else:
        # 情況 A：資料庫還沒更新今天的資料，最新交易日就是在途
        if latest_trading_date in data:
            return data[latest_trading_date], latest_trading_date
    
    return 0, None

def add_settlement_record(date, amount):
    """新增交易日的應收付記錄"""
    data = load_settlement_data()
    data[date] = amount
    save_settlement_data(data)

def render_t2_settlement_tracker():
    """渲染 T+2 在途應收付追蹤介面"""
    
    st.markdown("### 💰 T+2 在途應收付追蹤")
    
    # 取得最新交易日
    latest_trading_date = get_latest_trading_date()
    
    if not latest_trading_date:
        st.error("❌ 無法取得最新交易日，請確認資料庫中有台積電(2330)的資料")
        return
    
    st.info(f"📅 最新交易日: **{latest_trading_date}**")
    
    # === 區塊1: 實際餘額計算 ===
    st.markdown("#### 📊 區塊1: 實際帳戶餘額計算")
    
    # 取得在途應收付
    pending_amount, pending_date = get_pending_amount(latest_trading_date)
    
    # 第一行：在途應收付
    if pending_date:
        pending_display = f"{pending_amount:+,.0f}" if pending_amount != 0 else "0"
        st.markdown(f"""
        <div style='padding: 10px; background-color: #f8f9fa; border-radius: 5px; margin-bottom: 10px;'>
            <p style='font-size: 12px; color: #666; margin: 0;'>在途應收付 ({pending_date})</p>
            <p style='font-size: 20px; font-weight: bold; color: #333; margin: 5px 0 0 0;'>
                {pending_display} 元
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='padding: 10px; background-color: #f8f9fa; border-radius: 5px; margin-bottom: 10px;'>
            <p style='font-size: 12px; color: #666; margin: 0;'>在途應收付</p>
            <p style='font-size: 20px; font-weight: bold; color: #333; margin: 5px 0 0 0;'>
                0 元
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # 第二行：帳上餘額輸入
    # 初始化 session state
    if 'account_balance_calculated' not in st.session_state:
        st.session_state.account_balance_calculated = False
    if 'account_balance_result' not in st.session_state:
        st.session_state.account_balance_result = None
    
    # 使用 text_input 配合 on_change 來實現按 Enter 計算
    def on_account_balance_change():
        input_value = st.session_state.account_balance_text
        if input_value:
            try:
                balance = float(input_value)
                if balance > 0:
                    actual_balance = balance + pending_amount
                    st.session_state.account_balance_result = {
                        'account_balance': balance,
                        'pending_amount': pending_amount,
                        'actual_balance': actual_balance
                    }
                    st.session_state.account_balance_calculated = True
            except ValueError:
                pass
    
    st.text_input(
        "帳上餘額 (按 Enter 計算)",
        value="",
        key="account_balance_text",
        on_change=on_account_balance_change,
        help="輸入目前在銀行帳戶上看到的餘額，按 Enter 計算實際餘額",
        placeholder="輸入帳上餘額後按 Enter..."
    )
    
    # 計算並顯示實際餘額
    if st.session_state.account_balance_result is not None:
        result = st.session_state.account_balance_result
        account_balance = result['account_balance']
        pending_amount_calc = result['pending_amount']
        actual_balance = result['actual_balance']
        
        # 計算剩餘次數（每次約 45000）
        remaining_times = int(actual_balance / 45000)
        
        st.markdown("---")
        
        # 使用縮小字體顯示實際餘額（與在途應收付字體大小一致）
        balance_color = "green" if actual_balance >= account_balance else "red"
        st.markdown(f"""
        <div style='text-align: center; padding: 15px; background-color: #f0f2f6; border-radius: 10px; margin: 10px 0;'>
            <p style='font-size: 14px; color: #666; margin: 0;'>實際餘額</p>
            <p style='font-size: 20px; font-weight: bold; color: {balance_color}; margin: 8px 0;'>
                {actual_balance:,.0f} 元
            </p>
            <p style='font-size: 11px; color: #999; margin: 0;'>
                = 帳上餘額 {account_balance:,.0f} + 在途應收付 ({pending_amount_calc:+,.0f})
            </p>
            <p style='font-size: 14px; color: #0066cc; font-weight: bold; margin: 8px 0 0 0;'>
                剩 {remaining_times} 次 (45,000)
            </p>
            
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === 顯示歷史記錄 ===
    # 使用 checkbox 取代 expander（避免嵌套問題）
    show_history = st.checkbox("📋 顯示歷史記錄 (最近3筆)", value=False, key="show_settlement_history")
    
    if show_history:
        data = load_settlement_data()
        
        if data:
            st.markdown("| 交易日期 | 應收付金額 | 狀態 |")
            st.markdown("|---------|-----------|------|")
            
            # 使用「最新交易日」作為參考點
            reference_date = latest_trading_date
            
            sorted_dates = sorted(data.keys(), reverse=True)
            for date in sorted_dates:
                amount = data[date]
                amount_display = f"{amount:+,.0f}" if amount != 0 else "0"
                
                # 判斷記錄日期與最新交易日的關係
                if date > reference_date:
                    # 記錄日期晚於資料庫最新交易日（例如：今天記錄但資料庫還沒更新）
                    # 這是「今日記錄」，要到 T+2 才結算
                    status = "🔵 今日記錄 (T)"
                else:
                    # 記錄日期 <= 資料庫最新交易日
                    # 計算交易日差異
                    trading_days_diff = get_trading_days_diff(date, reference_date)
                    
                    # 根據交易日差異判斷狀態
                    if trading_days_diff == 0:
                        status = "🟡 在途中 (明早9點前結算)"
                    elif trading_days_diff == 1:
                        status = "🟢 已結清 (今早9點前已結算)"
                    elif trading_days_diff >= 2:
                        status = "⚪ 已完成"
                    else:
                        status = "🔜 未來記錄"
                
                st.markdown(f"| {date} | {amount_display} 元 | {status} |")
        else:
            st.info("尚無歷史記錄")
    
    st.markdown("---")
    
    # === 區塊2: 記錄當日應收付 ===
    st.markdown("#### 📝 區塊2: 記錄當日總應收付")
    
    # 初始化 session state
    if 'settlement_input_cleared' not in st.session_state:
        st.session_state.settlement_input_cleared = False
    if 'settlement_last_value' not in st.session_state:
        st.session_state.settlement_last_value = None
    if 'settlement_last_date' not in st.session_state:
        st.session_state.settlement_last_date = None
    
    # 使用 text_input 配合 on_change 來實現按 Enter 儲存
    def on_settlement_input_change():
        input_value = st.session_state.settlement_input_text
        if input_value:
            try:
                amount = float(input_value)
                if amount != 0:
                    # 使用今天的日期作為記錄日期
                    today_date = datetime.now().strftime('%Y-%m-%d')
                    add_settlement_record(today_date, amount)
                    st.session_state.settlement_last_value = amount
                    st.session_state.settlement_last_date = today_date
                    st.session_state.settlement_input_text = ""  # 清空輸入框
            except ValueError:
                pass
    
    st.text_input(
        "今日總應收付金額 (按 Enter 儲存)",
        value="",
        key="settlement_input_text",
        on_change=on_settlement_input_change,
        help="正數=應收(賣股)，負數=應付(買股)。例如: 買股花費10元輸入 -10，賣股收入20元輸入 20",
        placeholder="輸入金額後按 Enter..."
    )
    
    st.caption("💡 提示: 買股輸入負數(如 -10)，賣股輸入正數(如 20)，輸入後按 Enter 自動儲存")
    
    # 顯示儲存成功訊息
    if st.session_state.settlement_last_value is not None:
        st.success(f"✅ 已記錄 {st.session_state.settlement_last_date} 的應收付: {st.session_state.settlement_last_value:+,.0f} 元")
        st.session_state.settlement_last_value = None  # 清除訊息標記
        st.session_state.settlement_last_date = None

if __name__ == "__main__":
    st.set_page_config(page_title="T+2 在途應收付追蹤器", layout="wide")
    render_t2_settlement_tracker()
