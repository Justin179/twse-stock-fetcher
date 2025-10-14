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

def get_pending_amount(latest_trading_date):
    """取得在途應收付金額（前一個交易日的金額）"""
    data = load_settlement_data()
    
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
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 取得在途應收付
        pending_amount, pending_date = get_pending_amount(latest_trading_date)
        
        # 顯示在途應收付
        if pending_date:
            pending_display = f"{pending_amount:+,.0f}" if pending_amount != 0 else "0"
            st.metric(
                label=f"在途應收付 ({pending_date})",
                value=pending_display,
                delta=None,
                help="前一個交易日的應收付金額（T+1），明日將從帳戶扣款/入帳"
            )
        else:
            st.metric(
                label="在途應收付",
                value="0",
                help="無前一交易日的記錄"
            )
    
    with col2:
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
        
        st.markdown("---")
        
        # 使用大字體顯示實際餘額
        balance_color = "green" if actual_balance >= account_balance else "red"
        st.markdown(f"""
        <div style='text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin: 10px 0;'>
            <p style='font-size: 18px; color: #666; margin: 0;'>實際餘額</p>
            <p style='font-size: 36px; font-weight: bold; color: {balance_color}; margin: 10px 0;'>
                {actual_balance:,.0f} 元
            </p>
            <p style='font-size: 14px; color: #999; margin: 0;'>
                = 帳上餘額 {account_balance:,.0f} + 在途應收付 ({pending_amount_calc:+,.0f})
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
            
            sorted_dates = sorted(data.keys(), reverse=True)
            for i, date in enumerate(sorted_dates):
                amount = data[date]
                amount_display = f"{amount:+,.0f}" if amount != 0 else "0"
                
                # 判斷狀態
                if i == 0:
                    status = "🔵 今日記錄 (T)"
                elif i == 1:
                    status = "🟡 在途"
                elif i == 2:
                    status = "🟢 已結清 (早9後)"
                else:
                    status = ""
                
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
