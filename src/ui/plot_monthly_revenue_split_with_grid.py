import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Microsoft JhengHei"
plt.rcParams["axes.unicode_minus"] = False

def plot_monthly_revenue_split(stock_id, db_path="data/institution.db"):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT * FROM monthly_revenue
        WHERE stock_id = ?
        ORDER BY year_month DESC
        LIMIT 36
        """, conn, params=(stock_id,)
    )
    conn.close()

    if df.empty:
        print(f"⚠️ 無資料: {stock_id}")
        return

    df = df.sort_values("year_month")
    df["label"] = df["year_month"].astype(str).str[:4] + "/" + df["year_month"].astype(str).str[4:]
    x = range(len(df))

    # 年增率圖
    fig1, ax1 = plt.subplots(figsize=(12, 4), dpi=100)
    bars = ax1.bar(x, df["yoy_rate"], color=df["yoy_rate"].apply(lambda x: "red" if x >= 0 else "green"))
    ax1.set_ylabel("年增率 (%)", fontsize=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(df["label"], rotation=45)
    ax1.set_title(f"{stock_id} 年增率", fontsize=14)
    ax1.yaxis.grid(True, linestyle="--", alpha=0.3)  # 加上淡淡的橫向線
    plt.tight_layout()
    plt.show()

    # 營收圖
    fig2, ax2 = plt.subplots(figsize=(12, 4), dpi=100)
    ax2.bar(x, df["revenue"], color="brown")
    ax2.set_ylabel("營收 (百萬)", fontsize=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(df["label"], rotation=45)
    ax2.set_title(f"{stock_id} 營收", fontsize=14)
    ax2.yaxis.grid(True, linestyle="--", alpha=0.3)  # 營收圖也加上淡線
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_monthly_revenue_split("2535")
