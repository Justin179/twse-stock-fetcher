import pandas as pd
import sqlite3
import numpy as np
from datetime import datetime

def compute_rsi_wilder(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_minervini_rs(db_path="data/institution.db", table="twse_prices", months=12):
    conn = sqlite3.connect(db_path)

    df_meta = pd.read_sql_query("SELECT stock_id, name FROM stock_meta", conn)
    df_meta["stock_id"] = df_meta["stock_id"].astype(str)
    df_meta = df_meta[
        (~df_meta["stock_id"].str.startswith("0")) &
        (~df_meta["name"].str.endswith("-DR"))
    ]
    valid_ids = df_meta["stock_id"].tolist()

    query = f"""
    SELECT stock_id, date, close FROM {table}
    WHERE stock_id IN ({','.join(['?']*len(valid_ids))})
    """
    df = pd.read_sql_query(query, conn, params=valid_ids, parse_dates=["date"])
    conn.close()

    df["stock_id"] = df["stock_id"].astype(str)
    df = df.sort_values(by=["stock_id", "date"])
    df = df.dropna(subset=["close"])

    latest_date = df["date"].max()
    past_1y_date = latest_date - pd.DateOffset(months=months)
    year_start = datetime(latest_date.year, 1, 1)

    # === 計算 1Y 報酬率與 RS ===
    df_1y = df[df["date"] >= past_1y_date]
    returns_1y = (
        df_1y.groupby("stock_id").apply(
            lambda g: (g["close"].iloc[-1] - g["close"].iloc[0]) / g["close"].iloc[0]
        )
        .rename("return_1y")
        .reset_index()
    )
    returns_1y["rs_score_1y"] = returns_1y["return_1y"].rank(pct=True) * 100

    # === 計算 YTD 報酬率與 RS ===
    df_ytd = df[df["date"] >= pd.Timestamp(year_start)]
    returns_ytd = (
        df_ytd.groupby("stock_id").apply(
            lambda g: (g["close"].iloc[-1] - g["close"].iloc[0]) / g["close"].iloc[0]
        )
        .rename("return_ytd")
        .reset_index()
    )
    returns_ytd["rs_score_ytd"] = returns_ytd["return_ytd"].rank(pct=True) * 100

    # === RSI ===
    df_rsi_input = df[df["date"] >= (latest_date - pd.Timedelta(days=90))].copy()
    rsi_df = []
    for sid, group in df_rsi_input.groupby("stock_id"):
        group = group.sort_values("date")
        group["rsi14"] = compute_rsi_wilder(group["close"], period=14)
        rsi_value = group["rsi14"].iloc[-1] if not group["rsi14"].dropna().empty else np.nan
        rsi_df.append({"stock_id": sid, "rsi14": rsi_value})
    rsi_df = pd.DataFrame(rsi_df)

    # === 合併所有欄位 ===
    result = (
        returns_1y
        .merge(returns_ytd, on="stock_id", how="outer")
        .merge(rsi_df, on="stock_id", how="left")
        .merge(df_meta, on="stock_id", how="left")
    )

    result = result.round({
        "return_1y": 2,
        "rs_score_1y": 2,
        "return_ytd": 2,
        "rs_score_ytd": 2,
        "rsi14": 2
    })

    # === 寫入 SQLite ===
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_rs_rsi (
                stock_id TEXT PRIMARY KEY,
                name TEXT,
                return_1y REAL,
                rs_score_1y REAL,
                return_ytd REAL,
                rs_score_ytd REAL,
                rsi14 REAL
            )
        """)
        cursor.execute("DELETE FROM stock_rs_rsi")
        conn.commit()

        for _, row in result.iterrows():
            cursor.execute("""
                INSERT INTO stock_rs_rsi (
                    stock_id, name, return_1y, rs_score_1y,
                    return_ytd, rs_score_ytd, rsi14
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                row["stock_id"], row["name"],
                row.get("return_1y"), row.get("rs_score_1y"),
                row.get("return_ytd"), row.get("rs_score_ytd"),
                row.get("rsi14")
            ))
        conn.commit()

    print("✅ 計算完成，已寫入資料表 stock_rs_rsi")

if __name__ == "__main__":
    compute_minervini_rs()
