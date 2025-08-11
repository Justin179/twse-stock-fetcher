import streamlit as st
from pathlib import Path
import sqlite3
import pandas as pd
from html import escape  # 轉義，避免特殊字元破壞 HTML


def _load_id_name_map(db_path: str = "data/institution.db") -> dict:
    """讀取 stock_meta 並回傳 {stock_id: name}"""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT stock_id, name FROM stock_meta", conn)
    conn.close()
    return dict(zip(df["stock_id"].astype(str), df["name"]))


def render_temp_list_expander(
    temp_txt: str = "temp_list.txt",
    db_path: str = "data/institution.db",
    title: str = "📄 show temp_list",
    show_count: bool = True,
):
    """
    用 expander 顯示 temp_list.txt（代碼 + 名稱），
    每行附「📋」按鈕；點擊後只複製『代碼』並顯示 0.9s 提示。
    """
    with st.expander(title):
        p = Path(temp_txt)
        if not p.exists():
            st.warning(f"⚠️ 找不到 {temp_txt}")
            return

        # 讀檔：去空行、去 # 註解
        codes = [
            ln.strip()
            for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if not codes:
            st.info(f"{temp_txt} 為空")
            return

        id_name = _load_id_name_map(db_path)
        display_lines = [f"{c} {id_name.get(c, '')}".rstrip() for c in codes]

        # 逐行輸出（HTML/JS；JS 花括號轉義為 {{ }}）
        for i, (code, display) in enumerate(zip(codes, display_lines)):
            safe_display = escape(display)  # 顯示用
            # 放一個隱藏 span 存純代碼，copy 時讀它（避免 HTML entity 影響）
            html = f"""
<div style="display:flex;align-items:center;gap:8px;margin:6px 0;">
  <span id="mst-disp-{i}"
        style="font:13px/1.4 ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace;">
    {safe_display}
  </span>
  <span id="mst-code-{i}" style="display:none">{code}</span>
  <button
    style="border:1px solid #ddd;border-radius:8px;padding:4px 8px;background:#fff;cursor:pointer;"
    onclick="
      var txt = document.getElementById('mst-code-{i}').innerText;
      navigator.clipboard.writeText(txt).then(() => {{
        var t = document.createElement('div');
        t.textContent = '已複製：{code}';
        t.style.position='fixed'; t.style.right='16px'; t.style.bottom='16px';
        t.style.background='rgba(50,50,50,.92)'; t.style.color='#fff';
        t.style.padding='8px 12px'; t.style.borderRadius='10px'; t.style.zIndex='99999';
        t.style.font='13px system-ui';
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 900);
      }});
    ">
    📋
  </button>
</div>
"""
            st.components.v1.html(html, height=38)

        if show_count:
            st.caption(f"共 {len(display_lines)} 檔")
