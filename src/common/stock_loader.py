import sqlite3
import pandas as pd
import streamlit as st

# 讀取持股清單與公司名稱（可支援 refresh cache）
@st.cache_data(show_spinner=False)
def load_stock_list_with_names(file_path="my_stock_holdings.txt", db_path="data/institution.db", refresh=False):
    """讀取持股股票清單與名稱對照，回傳 stock_id 清單與顯示選項清單"""
    if refresh:
        st.cache_data.clear()

    with open(file_path, "r", encoding="utf-8") as f:
        stocks = sorted(
            line.strip() for line in f
            if line.strip() and not line.strip().startswith("#")
        )

    conn = sqlite3.connect(db_path)
    # 同時讀取名稱與市場別（市/櫃）
    df = pd.read_sql_query("SELECT stock_id, name, market FROM stock_meta", conn)
    conn.close()

    # 建立 {stock_id: (name, market)} 對照
    id_info_map = {
        str(row["stock_id"]): (row["name"], row.get("market")) if isinstance(row, dict) else (row["name"], row["market"])
        for _, row in df.iterrows()
    }

    def format_display(stock_id: str) -> str:
        """將代碼、名稱與市場別組成顯示文字，如 2330 台積電 (市)"""
        info = id_info_map.get(stock_id)
        if not info:
            return stock_id
        name, market = info
        market_suffix = ""
        if market in ("市", "櫃"):
            market_suffix = f" ({market})"
        return f"{stock_id} {name}{market_suffix}"

    display_options = [format_display(stock_id) for stock_id in stocks]
    return stocks, display_options
