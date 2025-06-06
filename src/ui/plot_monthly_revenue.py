import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Microsoft JhengHei"
plt.rcParams["axes.unicode_minus"] = False

def plot_monthly_revenue(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT * FROM monthly_revenue
        WHERE stock_id = ?
        ORDER BY year_month DESC
        LIMIT 24
        """, conn, params=(stock_id,)
    )
    conn.close()

    if df.empty:
        print(f"⚠️ 無資料: {stock_id}")
        return

    df = df.sort_values("year_month")
    df["label"] = df["year_month"].astype(str).str.slice(2)  # e.g. 2304, 2305
    x = range(len(df))

    fig, ax1 = plt.subplots(figsize=(12, 6), dpi=100)

    # 月營收（百萬）
    ax1.bar(x, df["revenue"], color="orange", label="月營收 (百萬)")
    ax1.set_ylabel("月營收 (百萬)", color="orange")
    ax1.tick_params(axis="y", labelcolor="orange")

    # 月營收年增率
    ax2 = ax1.twinx()
    ax2.plot(x, df["yoy_rate"], color="blue", marker="o", label="年增率 (%)")
    ax2.set_ylabel("年增率 (%)", color="blue")
    ax2.tick_params(axis="y", labelcolor="blue")

    # x軸標籤
    plt.xticks(x, df["label"], rotation=45)
    plt.title(f"{stock_id} 月營收與年增率 (近24個月)")
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_monthly_revenue("3017")
