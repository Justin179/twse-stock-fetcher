from collections import OrderedDict
from pathlib import Path
import sqlite3
from typing import Dict, Optional

import streamlit as st

from analyze.analyze_price_break_conditions_dataloader import get_today_prices


KEY_PRICE_FILE = "key_price.txt"
DB_PATH = "data/institution.db"


def _safe_float(value) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_price(value) -> str:
    number = _safe_float(value)
    if number is None:
        return "-"
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def load_key_price_map(file_path: str = KEY_PRICE_FILE) -> "OrderedDict[str, float]":
    entries: "OrderedDict[str, float]" = OrderedDict()
    path = Path(file_path)
    if not path.exists():
        return entries

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        stock_id, separator, price_text = line.partition(",")
        if not separator:
            continue

        stock_id = stock_id.strip()
        target_price = _safe_float(price_text.strip())
        if not stock_id or target_price is None:
            continue

        entries[stock_id] = target_price

    return entries


def write_key_price_map(entries: "OrderedDict[str, float]", file_path: str = KEY_PRICE_FILE) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"{stock_id},{_format_price(price)}" for stock_id, price in entries.items())
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def upsert_key_price(stock_id: str, target_price: float, file_path: str = KEY_PRICE_FILE) -> bool:
    entries = load_key_price_map(file_path=file_path)
    existed = stock_id in entries
    entries[stock_id] = target_price
    write_key_price_map(entries, file_path=file_path)
    return existed


def delete_key_price(stock_id: str, file_path: str = KEY_PRICE_FILE) -> bool:
    entries = load_key_price_map(file_path=file_path)
    if stock_id not in entries:
        return False
    del entries[stock_id]
    write_key_price_map(entries, file_path=file_path)
    return True


def clear_key_prices(file_path: str = KEY_PRICE_FILE) -> None:
    write_key_price_map(OrderedDict(), file_path=file_path)


@st.cache_data(show_spinner=False)
def load_stock_meta_map(db_path: str = DB_PATH) -> Dict[str, Dict[str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_id, name, market FROM stock_meta")
        rows = cursor.fetchall()
    finally:
        conn.close()

    return {
        str(stock_id): {
            "name": name or "",
            "market": market or "",
        }
        for stock_id, name, market in rows
    }


def format_stock_display(stock_id: str, stock_meta_map: Dict[str, Dict[str, str]]) -> str:
    info = stock_meta_map.get(stock_id, {})
    name = info.get("name", "")
    market = info.get("market", "")

    label = stock_id
    if name:
        label += f" {name}"
    if market in ("市", "櫃"):
        label += f" ({market})"
    return label


def _fetch_recent_daily_rows(stock_id: str, db_path: str = DB_PATH) -> list[dict]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, close, volume
            FROM twse_prices
            WHERE stock_id = ?
              AND close IS NOT NULL
              AND close > 0
            ORDER BY date DESC
            LIMIT 2
            """,
            (stock_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        {"date": row[0], "close": row[1], "volume": row[2]}
        for row in rows
    ]


def build_key_price_snapshot(stock_id: str, sdk=None, db_path: str = DB_PATH) -> Optional[dict]:
    try:
        today_info = get_today_prices(stock_id, sdk=sdk)
    except Exception:
        return None

    close_price = _safe_float(today_info.get("c1")) if isinstance(today_info, dict) else None
    previous_close = _safe_float(today_info.get("c2")) if isinstance(today_info, dict) else None
    if close_price is None or previous_close is None:
        return None

    current_volume = _safe_float(today_info.get("v")) if isinstance(today_info, dict) else None
    recent_rows = _fetch_recent_daily_rows(stock_id, db_path=db_path)

    if current_volume is None and recent_rows:
        latest_volume = _safe_float(recent_rows[0].get("volume"))
        if latest_volume is not None:
            current_volume = latest_volume / 1000.0

    yesterday_volume = None
    if recent_rows:
        api_date = str(today_info.get("date") or "") if isinstance(today_info, dict) else ""
        if len(recent_rows) >= 2 and recent_rows[0]["date"] == api_date:
            yest_volume = _safe_float(recent_rows[1].get("volume"))
        else:
            yest_volume = _safe_float(recent_rows[0].get("volume"))

        if yest_volume is not None:
            yesterday_volume = yest_volume / 1000.0

    return {
        "date": today_info.get("date") if isinstance(today_info, dict) else None,
        "close_price": close_price,
        "previous_close": previous_close,
        "current_volume": current_volume,
        "yesterday_volume": yesterday_volume,
    }


def evaluate_key_price_condition(stock_id: str, target_price: float, stock_meta_map: Dict[str, Dict[str, str]], sdk=None) -> Optional[dict]:
    snapshot = build_key_price_snapshot(stock_id, sdk=sdk)
    if snapshot is None:
        return None

    close_price = snapshot["close_price"]
    previous_close = snapshot["previous_close"]
    current_volume = snapshot["current_volume"]
    yesterday_volume = snapshot["yesterday_volume"]
    if current_volume is None or yesterday_volume is None:
        return None

    is_volume_up = current_volume > yesterday_volume
    if not is_volume_up:
        return None

    stock_label = format_stock_display(stock_id, stock_meta_map)
    close_text = _format_price(close_price)
    target_text = _format_price(target_price)

    if close_price > previous_close and close_price > target_price:
        return {
            "stock_id": stock_id,
            "signal": "價漲量增站上指定價格點位",
            "message": f"{stock_label} 收{close_text}帶量站上{target_text}",
        }

    if close_price < previous_close and close_price < target_price:
        return {
            "stock_id": stock_id,
            "signal": "價跌量增跌破指定價格點位",
            "message": f"{stock_label} 收{close_text}帶量跌破{target_text}",
        }

    return None


def render_key_price_checker(file_path: str = KEY_PRICE_FILE, db_path: str = DB_PATH, sdk=None) -> None:
    stock_meta_map = load_stock_meta_map(db_path=db_path)

    with st.expander("🎯 指定價格點位檢查", expanded=False):
        feedback_placeholder = st.empty()
        st.caption("盤中可先儲存股票代碼與價格點位，收盤後按 check 篩出帶量站上或帶量跌破指定點位的股票。")

        form_version = st.session_state.get("key_price_form_version", 0)
        stock_input_key = f"key_price_stock_id_input_{form_version}"
        price_input_key = f"key_price_target_price_input_{form_version}"

        with st.form("key_price_input_form", clear_on_submit=False):
            stock_id_input = st.text_input(
                "股票代碼",
                key=stock_input_key,
                placeholder="例如 2330",
            ).strip()
            target_price_input = st.text_input(
                "價格點位 x",
                key=price_input_key,
                placeholder="例如 1969",
            ).strip()

            if stock_id_input:
                st.caption(f"目前輸入：{format_stock_display(stock_id_input, stock_meta_map)}")

            form_col1, form_col2 = st.columns([1.8, 1])
            with form_col1:
                save_submitted = st.form_submit_button("儲存/覆蓋")
            with form_col2:
                execute_submitted = st.form_submit_button("執行")

        if save_submitted:
            target_price = _safe_float(target_price_input)
            if not stock_id_input:
                st.warning("請先輸入股票代碼。")
            elif target_price is None:
                st.warning("請輸入有效的價格點位。")
            else:
                existed = upsert_key_price(stock_id_input, target_price, file_path=file_path)
                action_text = "已覆蓋" if existed else "已新增"
                st.session_state["key_price_form_version"] = form_version + 1
                st.session_state["key_price_feedback"] = f"{action_text} {stock_id_input} → {_format_price(target_price)}"
                st.session_state["key_price_feedback_type"] = "success"
                st.session_state.pop(stock_input_key, None)
                st.session_state.pop(price_input_key, None)
                st.rerun()

        feedback_message = st.session_state.pop("key_price_feedback", None)
        feedback_type = st.session_state.pop("key_price_feedback_type", "success")
        if feedback_message:
            if feedback_type == "success":
                feedback_placeholder.success(feedback_message)
            elif feedback_type == "warning":
                feedback_placeholder.warning(feedback_message)
            else:
                feedback_placeholder.info(feedback_message)

        entries = load_key_price_map(file_path=file_path)

        if execute_submitted:
            above_results = []
            below_results = []
            skipped_count = 0

            for stock_id, target_price in entries.items():
                result = evaluate_key_price_condition(
                    stock_id=stock_id,
                    target_price=target_price,
                    stock_meta_map=stock_meta_map,
                    sdk=sdk,
                )
                if result is None:
                    skipped_count += 1
                    continue
                if result["signal"] == "價漲量增站上指定價格點位":
                    above_results.append(result)
                elif result["signal"] == "價跌量增跌破指定價格點位":
                    below_results.append(result)

            st.session_state["key_price_check_results_above"] = above_results
            st.session_state["key_price_check_results_below"] = below_results
            st.session_state["key_price_check_skipped_count"] = skipped_count

        if st.button("清空全部", key="clear_all_key_price_button"):
                clear_key_prices(file_path=file_path)
                st.session_state.pop("key_price_check_results_above", None)
                st.session_state.pop("key_price_check_results_below", None)
                st.session_state.pop("key_price_check_skipped_count", None)
                feedback_placeholder.success("已清空 key_price.txt")

        entries = load_key_price_map(file_path=file_path)

        if entries:
            st.markdown("**目前 key_price.txt**")
            for stock_id, target_price in entries.items():
                item_col1, item_col2 = st.columns([5, 1])
                with item_col1:
                    st.write(f"- {format_stock_display(stock_id, stock_meta_map)} , x = {_format_price(target_price)}")
                with item_col2:
                    if st.button("刪除", key=f"delete_key_price_{stock_id}", use_container_width=True):
                        deleted = delete_key_price(stock_id, file_path=file_path)
                        st.session_state.pop("key_price_check_results_above", None)
                        st.session_state.pop("key_price_check_results_below", None)
                        st.session_state.pop("key_price_check_skipped_count", None)
                        if deleted:
                            feedback_placeholder.success(f"已刪除 {stock_id}")
                            st.rerun()
        else:
            st.info("目前尚未設定任何指定價格點位。")

        if "key_price_check_results_above" in st.session_state or "key_price_check_results_below" in st.session_state:
            above_results = st.session_state.get("key_price_check_results_above", [])
            below_results = st.session_state.get("key_price_check_results_below", [])
            skipped_count = st.session_state.get("key_price_check_skipped_count", 0)

            st.markdown("**check 結果**")
            if above_results:
                st.markdown("**站上**")
                for item in above_results:
                    st.write(f"- {item['message']}")

            if below_results:
                st.markdown("**跌破**")
                for item in below_results:
                    st.write(f"- {item['message']}")

            if not above_results and not below_results:
                st.info("本次沒有符合條件的股票。")

            if skipped_count:
                st.caption(f"有 {skipped_count} 檔未觸發條件或資料不足，因此未列出。")