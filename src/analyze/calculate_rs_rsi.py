import pandas as pd
import sqlite3
import numpy as np
from pathlib import Path

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

    # 排除 stock_id 以 0 開頭（ETF），以及名稱以 -DR 結尾（DR 股票）
    df_meta = pd.read_sql_query("SELECT stock_id, name FROM stock_meta", conn)
    df_meta["stock_id"] = df_meta["stock_id"].astype(str)
    df_meta = df_meta[
        (~df_meta["stock_id"].str.startswith("0")) &     # 排除 ETF
        (~df_meta["name"].str.endswith("-DR"))           # 排除 DR
    ]
    valid_ids = df_meta["stock_id"].tolist()

    # 抓取股價資料
    query = f"""
    SELECT stock_id, date, close FROM {table}
    WHERE stock_id IN ({','.join(['?']*len(valid_ids))})
    """
    df = pd.read_sql_query(query, conn, params=valid_ids, parse_dates=["date"])
    conn.close()

    df = df.sort_values(by=["stock_id", "date"])
    df = df.dropna(subset=["close"])

    latest_date = df["date"].max()
    past_date = latest_date - pd.DateOffset(months=months)

    # 保留最近 N 個月資料
    df_recent = df[df["date"] >= past_date]

    # 計算報酬率
    returns = (
        df_recent.groupby("stock_id").apply(
            lambda g: (g["close"].iloc[-1] - g["close"].iloc[0]) / g["close"].iloc[0]
        )
        .rename("return")
        .reset_index()
    )

    # RS 百分等級（0~100）
    returns["rs_score"] = returns["return"].rank(pct=True) * 100

    # RSI 計算（90 天內）
    df_rsi_input = df[df["date"] >= (latest_date - pd.Timedelta(days=90))].copy()
    rsi_df = []
    for sid, group in df_rsi_input.groupby("stock_id"):
        group = group.sort_values("date")
        group["rsi14"] = compute_rsi_wilder(group["close"], period=14)
        rsi_value = group["rsi14"].iloc[-1] if not group["rsi14"].dropna().empty else np.nan
        rsi_df.append({"stock_id": sid, "rsi14": rsi_value})
    rsi_df = pd.DataFrame(rsi_df)

    # 合併資料
    result = pd.merge(returns, rsi_df, on="stock_id", how="left")

    # 四捨五入到小數點後兩位
    result = result.round({
        "return": 2,
        "rs_score": 2,
        "rsi14": 2
    })

    return result

if __name__ == "__main__":
    df = compute_minervini_rs()
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    df.to_csv(output_dir / "rs_rsi_result.csv", index=False)
    print("✅ RS + RSI 結果已輸出至 output/rs_rsi_result.csv")
