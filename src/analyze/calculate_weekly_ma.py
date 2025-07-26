import pandas as pd

def calculate_weekly_ma(df: pd.DataFrame, weeks=5) -> pd.Series:
    """
    根據每週最後一個交易日的收盤價計算週均線。
    傳回一個 Series，index 是每週的最後一個交易日，值是週均線。
    """
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df["year_week"] = df.index.to_series().apply(
        lambda d: f"{d.isocalendar().year}-{d.isocalendar().week:02d}"
    )
    last_per_week = df.groupby("year_week").tail(1).copy()
    last_per_week[f"WMA{weeks}"] = last_per_week["Close"].rolling(window=weeks).mean()
    return last_per_week[[f"WMA{weeks}"]].set_index(last_per_week.index)
