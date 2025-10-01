# -*- coding: utf-8 -*-
# tx_near_month_finmind.py  — 取得指定日期 台指期(TX) 近月合約價格（用 FinMind）
from datetime import datetime, date
from typing import Tuple, Optional
import re
import requests
import pandas as pd

FINMIND_API = "https://api.finmindtrade.com/api/v4/data"

def _parse_contract_date(x) -> Optional[date]:
    """支援 'YYYYMM' 或 'YYYY-MM-DD' 或一般日期字串"""
    if pd.isna(x):
        return None
    s = str(x).strip()
    # 202510 → 2025-10-01 當月第一天當作代表
    if re.fullmatch(r"\d{6}", s):
        return datetime.strptime(s, "%Y%m").date().replace(day=1)
    # 2025-10-01 直接解析
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return datetime.strptime(s, "%Y-%m-%d").date()
    # 其他交給 pandas（盡量容錯）
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None

def get_tx_near_month_price_on(the_date: date,
                               token: Optional[str] = None) -> Tuple[str, float]:
    """
    回傳: (近月契約YYYYMM, 當日價格)
    資料源: FinMind TaiwanFuturesDaily（data_id='TX'）
    價格欄位優先順序: settlement_price → close → close_price → end_price
    """
    ds = the_date.strftime("%Y-%m-%d")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {
        "dataset": "TaiwanFuturesDaily",
        "data_id": "TX",
        "start_date": ds,
        "end_date": ds,
    }
    r = requests.get(FINMIND_API, headers=headers, params=params, timeout=20)
    j = r.json()
    if not j.get("data"):
        raise RuntimeError(f"FinMind 回傳空資料: {j.get('msg') or 'no data'}")

    df = pd.DataFrame(j["data"])

    # 只留當日
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[df["date"] == the_date]

    # 只留日盤 / 一般盤（欄位可能叫 trading_session）
    if "trading_session" in df.columns:
        df = df[df["trading_session"].isin(["regular", "position", "day"])]

    if df.empty:
        raise RuntimeError("指定日期沒有台指期日盤資料")

    # 解析合約到期欄（可能是 YYYYMM）
    if "contract_date" not in df.columns:
        raise RuntimeError("缺少 contract_date 欄位")
    df["contract_date_parsed"] = df["contract_date"].map(_parse_contract_date)
    df = df.dropna(subset=["contract_date_parsed"])
    if df.empty:
        raise RuntimeError("contract_date 欄位格式無法解析")

    # 近月 = contract_date 最早者
    row = df.loc[df["contract_date_parsed"].idxmin()]

    # 取價格
    price = None
    for col in ("settlement_price", "close", "close_price", "end_price"):
        if col in df.columns and pd.notna(row.get(col)):
            price = float(row[col])
            break
    if price is None:
        raise RuntimeError("找不到價格欄位（settlement/close）")

    ym = row["contract_date_parsed"].strftime("%Y%m")
    return ym, price

if __name__ == "__main__":
    # 範例：抓 2025-10-01
    dt = datetime.strptime("2025-10-01", "%Y-%m-%d").date()
    ym, px = get_tx_near_month_price_on(dt)
    print(f"{dt} 台指期近月({ym}) 價格: {px}")
