import sqlite3
import pandas as pd
from datetime import datetime
import sys, os
from common.login_helper import get_logged_in_dl, get_logged_in_sdk
from FinMind.data import DataLoader
from fetch.finmind.finmind_db_fetcher import fetch_with_finmind_recent
from common.time_utils import is_fubon_api_maintenance_time


DB_PATH = "data/institution.db" 


def get_recent_hl_before_date(stock_id: str, before_date: str, limit: int = 3) -> pd.DataFrame:
        """取得 before_date(不含) 之前最近 N 根日K的 high/low。

        用途：
            - 今日三盤：用 today_date 為 before_date，取 [昨、前] 兩根
            - 昨日三盤：同一批資料取 [前、前前] 兩根
        """
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
                """
                SELECT date, high, low
                FROM twse_prices
                WHERE stock_id = ? AND date < ?
                ORDER BY date DESC
                LIMIT ?
                """,
                conn,
                params=(stock_id, before_date, int(limit)),
        )
        conn.close()
        return df
def get_recent_prices(stock_id, today_date):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT date, close, high, low, volume 
        FROM twse_prices 
        WHERE stock_id = ? AND date < ? 
        ORDER BY date DESC LIMIT 2
        """,
        conn, params=(stock_id, today_date)
    )
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_yesterday_hl(stock_id, today_date):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT date, high, low 
        FROM twse_prices 
        WHERE stock_id = ? AND date < ? 
        ORDER BY date DESC LIMIT 1
        """,
        conn, params=(stock_id, today_date)
    )
    conn.close()
    if len(df) < 1:
        return None, None
    return df.iloc[0]["high"], df.iloc[0]["low"]


def get_week_month_high_low(stock_id):
    today = datetime.today()
    current_year, current_week, _ = today.isocalendar()

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT date, high, low
        FROM twse_prices
        WHERE stock_id = ?
        AND close IS NOT NULL
        AND close != 0
        """,
        conn, params=(stock_id,)
    )

    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.isocalendar().year
    df["week"] = df["date"].dt.isocalendar().week
    df["month"] = df["date"].dt.month

    # 上週
    prev_week = current_week - 1
    year = current_year
    for _ in range(10):
        week_df = df[(df["year"] == year) & (df["week"] == prev_week)]
        if not week_df.empty:
            w1 = week_df["high"].max()
            w2 = week_df["low"].min()
            break
        prev_week -= 1
        if prev_week <= 0:
            year -= 1
            prev_week = 52
    else:
        w1 = w2 = None

    # 上月
    prev_month = today.month - 1 or 12
    prev_month_year = today.year - 1 if today.month == 1 else today.year
    month_df = df[(df["date"].dt.year == prev_month_year) & (df["date"].dt.month == prev_month)]

    if not month_df.empty:
        m1 = month_df["high"].max()
        m2 = month_df["low"].min()
    else:
        m1 = m2 = None

    # print(f"📊 {stock_id} 上週高低：{w1}, {w2}；上月高低：{m1}, {m2}")
    return w1, w2, m1, m2


def get_latest_price_from_db(stock_id):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT date, open, close
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date DESC LIMIT 2
        """,
        conn, params=(stock_id,)
    )
    conn.close()

    if len(df) < 2:
        raise ValueError("資料庫中無足夠的資料供替代使用")

    today_row = df.iloc[0]
    prev_row = df.iloc[1]

    return {
        "date": today_row["date"],
        "c1": today_row["close"],
        "o": today_row["open"],
        "c2": prev_row["close"]  # 第二新資料的收盤價為 c2
    }

def get_today_prices(stock_id, sdk=None):
    """
    回傳：
      {
        "date": "YYYY-MM-DD",
        "c1": <盤中現價 closePrice>,
        "o":  <openPrice>,
        "c2": <previousClose>,
        "h":  <highPrice>,
        "l":  <lowPrice>,
        "v":  <成交量(張) = total.tradeVolume>
      }
    富邦 API 維護/失敗時，改走 DB fallback（僅保證 date/c1/o/c2）。
    """
    if is_fubon_api_maintenance_time():
        # print("⚠️ 富邦 API 維護時間，改用資料庫 fallback")
        return get_latest_price_from_db(stock_id)

    try:
        if sdk is None:
            sdk = get_logged_in_sdk()
        sdk.init_realtime()

        quote = sdk.marketdata.rest_client.stock.intraday.quote(symbol=stock_id)

        # volume 在 total.tradeVolume，保留頂層 volume 作為備援
        vol = (quote.get("total") or {}).get("tradeVolume")
        if vol is None:
            vol = quote.get("volume")

        # 🔎 檢查完整性（API 路徑）
        need_ok = all([
            quote.get("date"),
            quote.get("closePrice") is not None,
            quote.get("openPrice") is not None,
            quote.get("previousClose") is not None,
            quote.get("highPrice") is not None,
            quote.get("lowPrice") is not None,
            vol is not None,
        ])
        if not need_ok:
            raise ValueError("富邦 API 回傳欄位不完整，改用 DB fallback")

        return {
            "date": quote.get("date"),
            "c1":   quote.get("closePrice"),
            "o":    quote.get("openPrice"),
            "c2":   quote.get("previousClose"),
            "h":    quote.get("highPrice"),
            "l":    quote.get("lowPrice"),
            "v":    vol,  # ← 成交量(張)
        }

    except Exception as e:
        print(f"⚠️ 富邦 API 失敗，改用資料庫 fallback：{e}")
        return get_latest_price_from_db(stock_id)



def analyze_stock(stock_id, dl=None, sdk=None):

    if dl is None:
        dl = get_logged_in_dl()
    
    fetch_with_finmind_recent(stock_id, dl, months=2) # 
    
    today = get_today_prices(stock_id, sdk=sdk)
    today_date = today["date"]  # 這是今天的日期字串

    db_data = get_recent_prices(stock_id, today_date)
    w1, w2, m1, m2 = get_week_month_high_low(stock_id)
    h, l = get_yesterday_hl(stock_id, today_date)

    c1, o, c2 = today["c1"], today["o"], today["c2"]
    v1 = db_data.iloc[0]["volume"] if len(db_data) > 0 else None
    v2 = db_data.iloc[1]["volume"] if len(db_data) > 1 else None

    signals = []

    def _safe_float(v):
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    def _get_today_volume_status(today_info: dict, y_volume_in_shares: float) -> str:
        """判斷「今三盤」是否量增/量縮：沿用 UI 的盤中預估邏輯；盤後直接比今量>=昨量。

        - today_info['v'] 單位：張（盤中 API）
        - y_volume_in_shares 單位：股（DB）
        """
        try:
            from ui.volume_forecast import (
                get_trading_minutes_elapsed,
                forecast_by_avg_rate,
                forecast_by_time_segment,
            )
        except Exception:
            get_trading_minutes_elapsed = None
            forecast_by_avg_rate = None
            forecast_by_time_segment = None

        today_v = _safe_float(today_info.get("v")) if isinstance(today_info, dict) else None
        y_v = _safe_float(y_volume_in_shares)
        if y_v is not None:
            y_v = y_v / 1000.0  # 股 -> 張

        # 1) 交易時間內：用預估模組判斷
        try:
            if get_trading_minutes_elapsed is not None:
                elapsed = get_trading_minutes_elapsed()
                if (
                    elapsed is not None
                    and elapsed > 0
                    and elapsed < 270
                    and today_v is not None
                    and y_v is not None
                    and y_v > 0
                    and forecast_by_avg_rate is not None
                    and forecast_by_time_segment is not None
                ):
                    forecast1 = forecast_by_avg_rate(today_v, y_v)
                    forecast2 = forecast_by_time_segment(today_v, y_v)
                    if forecast1 and forecast2:
                        method1_increase = forecast1.get("forecast_pct") is not None and forecast1["forecast_pct"] >= 100
                        method2_increase = forecast2.get("status") == "ahead"
                        if method1_increase == method2_increase:
                            return "量增" if method1_increase else "量縮"
                        return "量增" if method1_increase else "量縮"
        except Exception:
            pass

        # 2) 盤後或無法預估：直接比今量 vs 昨量
        if today_v is not None and y_v is not None:
            return "量增" if today_v >= y_v else "量縮"

        return "量縮"

    # --- 三盤突破 / 三盤跌破（昨/今） ---
    # 定義：
    # - 今三盤突破：c1 > max(昨日高, 前一日高)
    # - 今三盤跌破：c1 < min(昨日低, 前一日低)
    # - 昨三盤突破：c2 > max(前一日高, 前前一日高)
    # - 昨三盤跌破：c2 < min(前一日低, 前前一日低)
    def _to_float(v):
        return _safe_float(v)

    three_bar_term = None
    try:
        prev_hl = get_recent_hl_before_date(stock_id, today_date, limit=3)
        prev_hl = prev_hl.reset_index(drop=True)

        c1_f = _to_float(c1)
        c2_f = _to_float(c2)

        today_term = None
        yesterday_term = None
        today_break = None   # "突破" | "跌破" | None
        yday_break = None    # "突破" | "跌破" | None

        # 今：需要 (昨、前) 兩根
        if (c1_f is not None) and (len(prev_hl) >= 2):
            y_high = _to_float(prev_hl.iloc[0]["high"])
            y_low = _to_float(prev_hl.iloc[0]["low"])
            p_high = _to_float(prev_hl.iloc[1]["high"])
            p_low = _to_float(prev_hl.iloc[1]["low"])

            if (y_high is not None) and (p_high is not None) and (c1_f > max(y_high, p_high)):
                today_break = "突破"
            elif (y_low is not None) and (p_low is not None) and (c1_f < min(y_low, p_low)):
                today_break = "跌破"

        # 昨：需要 (前、前前) 兩根
        if (c2_f is not None) and (len(prev_hl) >= 3):
            p_high = _to_float(prev_hl.iloc[1]["high"])
            p_low = _to_float(prev_hl.iloc[1]["low"])
            pp_high = _to_float(prev_hl.iloc[2]["high"])
            pp_low = _to_float(prev_hl.iloc[2]["low"])

            if (p_high is not None) and (pp_high is not None) and (c2_f > max(p_high, pp_high)):
                yday_break = "突破"
            elif (p_low is not None) and (pp_low is not None) and (c2_f < min(p_low, pp_low)):
                yday_break = "跌破"

        # === 納入成交量（帶量） ===
        # 今三盤：用盤中預估/盤後直接比今量>=昨量
        if today_break:
            vol_status_today = _get_today_volume_status(today, v1)
            if vol_status_today == "量增":
                today_term = f"三盤<b>帶量</b>{today_break}"
            else:
                today_term = f"三盤{today_break}"

        # 昨三盤：直接用 DB 比較 c2 當天量 vs 前一交易日量
        if yday_break:
            v1_f = _safe_float(v1)
            v2_f = _safe_float(v2)
            if (v1_f is not None) and (v2_f is not None) and (v1_f >= v2_f):
                yesterday_term = f"三盤<b>帶量</b>{yday_break}"
            else:
                yesterday_term = f"三盤{yday_break}"

        if yesterday_term or today_term:
            if yesterday_term and today_term:
                three_bar_term = f"昨{yesterday_term} ┃ 今{today_term}"
            elif yesterday_term:
                three_bar_term = f"昨{yesterday_term}"
            elif today_term:
                three_bar_term = f"今{today_term}"
    except Exception:
        # 資料不足或 DB 讀取失敗時，直接略過不影響其他訊號
        pass

    # 今天開盤
    if o and c2:
        is_break_yesterday_high = h and o > h
        is_break_yesterday_low = l and o < l

        # 優先判斷過昨高/破昨低
        if is_break_yesterday_high:
            signals.append(f"今開盤({o}) 過昨高")
        elif is_break_yesterday_low:
            signals.append(f"今開盤({o}) 破昨低")
        else:
            # 若沒過昨高也沒破昨低，才檢查開高/平/低
            if o > c2:
                signals.append(f"今開盤({o}) 開高")
            elif o == c2:
                signals.append(f"今開盤({o}) 開平盤")
            elif o < c2:
                signals.append(f"今開盤({o}) 開低")

    # 讓「三盤突破/跌破」顯示在「今開盤...」的下一行（圖2藍圈位置）
    if three_bar_term:
        signals.append(three_bar_term)


    # 今天盤中
    if c1:
        if h and c1 > h:
            signals.append("今收盤(現價) 過昨高")
        if l and c1 < l:
            signals.append("今收盤(現價) 破昨低")
        if w1 and c1 > w1:
            signals.append("今收盤(現價) 過上週高點")
        if w2 and c1 < w2:
            signals.append("今收盤(現價) 破上週低點")
        if m1 and c1 > m1:
            signals.append("今收盤(現價) 過上月高點")
        if m2 and c1 < m2:
            signals.append("今收盤(現價) 破上月低點")


    # 昨天收盤
    if c2:
        # 上週高點
        if w1 and c2 > w1:
            if v1 and v2 and v1 > v2:
                signals.append(f"昨收盤({c2}) 帶量過上週高點")
            else:
                signals.append(f"昨收盤({c2}) 過上週高點")

        # 上月高點
        if m1 and c2 > m1:
            if v1 and v2 and v1 > v2:
                signals.append(f"昨收盤({c2}) 帶量過上月高點")
            else:
                signals.append(f"昨收盤({c2}) 過上月高點")

        # 上週低點
        if w2 and c2 < w2:
            if v1 and v2 and v1 > v2:
                signals.append(f"昨收盤({c2}) 帶量破上週低點")
            else:
                signals.append(f"昨收盤({c2}) 破上週低點")

        # 上月低點
        if m2 and c2 < m2:
            if v1 and v2 and v1 > v2:
                signals.append(f"昨收盤({c2}) 帶量破上月低點")
            else:
                signals.append(f"昨收盤({c2}) 破上月低點")


    return signals

if __name__ == "__main__":
    stock_id = "3017"
    results = analyze_stock(stock_id)
    print(f"📢 [{stock_id}] 提示訊號：")
    for r in results:
        print("✅", r)