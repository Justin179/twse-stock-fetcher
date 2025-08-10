# src/ui/collect_stock_button.py
import streamlit as st
from pathlib import Path
import pandas as pd
from typing import List, Dict

def _read_codes_csv(path: Path) -> pd.Series:
    s = pd.read_csv(path, header=None, encoding="utf-8-sig")[0].astype(str)
    s = s.str.strip()
    s = s[s.ne("")]
    s = s.str.replace(r"\.TW$", "", regex=True)
    return s

def _collect_and_write_with_single_blank_line(
    output_dir: str = "output",
    source_files: List[str] | None = None,
    temp_txt: str = "temp_list.txt",
) -> Dict:
    if source_files is None:
        source_files = [
            "匯入XQ_rs90強勢股.csv",
            "匯入XQ_籌碼集中度.csv",
            "過上週上月高個股.csv",
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

    all_codes = pd.concat(series_list, ignore_index=True)

    # 找出重複（跨檔或同檔）
    dup_mask = all_codes.duplicated(keep=False)
    duplicates = sorted(all_codes[dup_mask].unique().tolist())

    # 去重（保持原出現順序）
    unique_codes = all_codes.drop_duplicates().tolist()

    # 讀取既有內容並規整尾端換行：確保「只留一行空白行」再接新清單
    temp_path = Path(temp_txt)
    existing = temp_path.read_text(encoding="utf-8") if temp_path.exists() else ""
    new_block = ("\n".join(unique_codes) + "\n") if unique_codes else ""

    if existing == "":
        new_content = new_block
    else:
        # 移除所有結尾換行，然後補上剛好兩個 \n（=一個空白行）再接新區塊
        existing = existing.rstrip("\n")
        new_content = existing + "\n\n" + new_block

    # 以覆寫方式寫回，保證尾端僅一行空白行隔開
    temp_path.write_text(new_content, encoding="utf-8")

    return {
        "appended": len(unique_codes),
        "duplicates": duplicates,
        "missing": missing,
        "written_codes": unique_codes,
    }

def render_collect_stock_button(
    label: str = "🧺 匯集個股清單",
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
            st.success(f"✅ 已匯集 {appended} 檔個股並寫入 {temp_txt}（在原最後一行後**僅**留一行空白行再追加）。")
        else:
            warn_msg = "未追加任何個股。"
            if missing:
                warn_msg += "（來源檔缺少：" + "、".join(missing) + "）"
            st.warning(warn_msg)

        if duplicates:
            with st.expander("🔁 發現重複的個股代碼（點開查看）"):
                st.write("、".join(duplicates))
        if missing:
            st.info("ℹ️ 未找到的來源檔案：" + "、".join(missing))
