# src/ui/collect_stock_button.py
import streamlit as st
from pathlib import Path
import pandas as pd
from typing import List, Dict
import time  # 置中提示要用到短暫延遲

def _read_codes_csv(path: Path) -> pd.Series:
    s = pd.read_csv(path, header=None, encoding="utf-8-sig")[0].astype(str)
    s = s.str.strip()
    s = s[s.ne("")]
    # 同時拿掉 .TW 與 .TWO 字尾
    s = s.str.replace(r"\.TW[O]?$", "", regex=True)
    return s

def _collect_and_write_with_single_blank_line(
    output_dir: str = "output",
    source_files: List[str] | None = None,
    temp_txt: str = "temp_list.txt",
) -> Dict:
    # 定義優先順序：將「籌碼集中且趨勢向上.csv」排在第一位，以保留其排序
    if source_files is None:
        source_files = [
            "籌碼集中且趨勢向上.csv",
            "匯入XQ_rs90強勢股.csv",
            "匯入XQ_籌碼集中度.csv",
            "匯入XQ_過上月高點.csv",
        ]

    out_dir = Path(output_dir)
    series_list = []
    missing = []

    for name in source_files:
        p = out_dir / name
        if p.exists():
            series_list.append(_read_codes_csv(p))
        else:
            missing.append(name)

    if not series_list:
        return {"appended": 0, "duplicates": [], "missing": missing, "written_codes": []}

    # 合併所有清單
    # pandas 的 drop_duplicates 會保留「第一次出現」的項目。
    # 因為我們把「籌碼集中且趨勢向上.csv」放在 series_list 的最前面，
    # 它的個股與排序會被完整保留，後面重複出現的個股會被自動捨棄。
    all_codes = pd.concat(series_list, ignore_index=True)

    # 找出重複（僅供訊息顯示，不影響寫入）
    dup_mask = all_codes.duplicated(keep=False)
    duplicates = sorted(all_codes[dup_mask].unique().tolist())

    # 去重（關鍵：pandas 會保留第一個出現的項目，也就是優先保留主體檔案的代碼與位置）
    unique_codes = all_codes.drop_duplicates(keep='first').tolist()

    
    temp_path = Path(temp_txt)

    # 直接清空並覆寫（不保留原內容）
    new_content = "\n".join(unique_codes) + "\n" if unique_codes else ""

    # 讀取既有內容並規整尾端換行：確保「只留一行空白行」再接新清單（保留原內容）
    # existing = temp_path.read_text(encoding="utf-8") if temp_path.exists() else ""
    # new_block = ("\n".join(unique_codes) + "\n") if unique_codes else ""
    # if existing == "":
    #     new_content = new_block
    # else:
    #     existing = existing.rstrip("\n")
    #     new_content = existing + "\n\n" + new_block


    temp_path.write_text(new_content, encoding="utf-8")

    return {
        "appended": len(unique_codes),
        "duplicates": duplicates,
        "missing": missing,
        "written_codes": unique_codes,
    }

def show_center_toast(msg: str, seconds: float = 2.0):
    """在畫面中央顯示短暫提示，seconds 秒後自動消失。"""
    ph = st.empty()
    ph.markdown(
        f"""
        <div class="mst-center-toast">{msg}</div>
        <style>
        .mst-center-toast {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(50, 50, 50, 0.95);
            color: #fff;
            padding: 10px 16px;
            border-radius: 10px;
            box-shadow: 0 6px 18px rgba(0,0,0,.25);
            z-index: 10000;
            font-size: 15px;
            line-height: 1.3;
            white-space: nowrap;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(seconds) 
    ph.empty()


def render_collect_stock_button(
    label: str = "💎 匯集個股到temp_list",
    output_dir: str = "output",
    source_files: List[str] | None = None,
    temp_txt: str = "temp_list.txt",
):
    if st.button(label):
        result = _collect_and_write_with_single_blank_line(output_dir, source_files, temp_txt)
        appended = result["appended"]
        duplicates = result["duplicates"]
        missing = result["missing"]

        if appended > 0:
            show_center_toast(f"✅ 已匯集 {appended} 檔個股並寫入 {temp_txt}", seconds=2)
        else:
            warn_msg = "未追加任何個股"
            if missing:
                warn_msg += "（來源檔缺少：" + "、".join(missing) + "）"
            show_center_toast("⚠️ " + warn_msg, seconds=2)

        if duplicates:
            with st.expander("🔁 發現重複的個股代碼（點開查看）"):
                st.write("、".join(duplicates))
        if missing:
            st.info("ℹ️ 未找到的來源檔案：" + "、".join(missing))
