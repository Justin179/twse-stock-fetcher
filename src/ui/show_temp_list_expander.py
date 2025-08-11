import streamlit as st
from pathlib import Path

def render_temp_list_expander(temp_txt: str = "temp_list.txt", title: str = "📄 show temp_list"):
    """用 expander 顯示 temp_list.txt 的內容"""
    with st.expander(title):
        p = Path(temp_txt)
        if not p.exists():
            st.warning(f"⚠️ 找不到 {temp_txt}")
            return
        
        # 讀取檔案內容並去除空行
        stocks_in_temp = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        
        if stocks_in_temp:
            st.write(stocks_in_temp)
            st.caption(f"共 {len(stocks_in_temp)} 檔")
        else:
            st.info(f"{temp_txt} 為空")
