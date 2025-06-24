import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import sqlite3

# 修正中文顯示
matplotlib.rcParams['font.family'] = 'Microsoft JhengHei'
matplotlib.rcParams['axes.unicode_minus'] = False

def count_strong_days(df):
    if len(df) < 15:
        return 0, []

    df = df.sort_values(by='日期').tail(15).reset_index(drop=True)
    strong_days = 0
    strong_dates = []

    for i in range(5, len(df)):
        close_N = df.loc[i, '收盤價']
        close_N_1 = df.loc[i - 1, '收盤價']
        volume_N = df.loc[i, '成交量']
        volume_N_1 = df.loc[i - 1, '成交量']
        close_N_4 = df.loc[i - 4, '收盤價']
        close_N_5 = df.loc[i - 5, '收盤價']

        cond1 = close_N_4 > close_N_5
        cond2 = close_N > close_N_1 and volume_N > volume_N_1

        if cond1 and cond2:
            strong_days += 1
            strong_dates.append(df.loc[i, '日期'].strftime("%Y-%m-%d"))

    return strong_days, strong_dates

def plot_strong_days(df, strong_dates, stock_id="2330"):
    df['是否強勢日'] = df['日期'].isin(pd.to_datetime(strong_dates))
    plot_df = df.tail(10).copy()

    plt.figure(figsize=(10, 6))
    plt.plot(plot_df['日期'], plot_df['收盤價'], marker='o', label='收盤價')

    for i, row in plot_df.iterrows():
        if row['是否強勢日']:
            plt.scatter(row['日期'], row['收盤價'], color='red', s=100,
                        label='強勢日' if '強勢日' not in plt.gca().get_legend_handles_labels()[1] else "")

    plt.title(f'{stock_id} 近十交易日 強勢日視覺化')
    plt.xlabel('日期')
    plt.ylabel('收盤價')
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.text(
        0.01, -0.2,
        '強勢日: 扣抵日收高，當天價漲量增',
        fontsize=12,
        transform=plt.gca().transAxes
    )
    plt.show()

def main():
    stock_id = "2344"
    conn = sqlite3.connect("data/institution.db")
    query = """
        SELECT date AS 日期, close AS 收盤價, volume AS 成交量
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date
    """
    try:
        df = pd.read_sql_query(query, conn, params=(stock_id,))
        conn.close()

        df['日期'] = pd.to_datetime(df['日期'])
        df = df[['日期', '收盤價', '成交量']].dropna()

        count, dates = count_strong_days(df)
        print(f"\n📈 {stock_id} 強勢日次數：{count}，日期：{dates}")
        plot_strong_days(df, dates, stock_id)

    except Exception as e:
        print(f"⚠️ 發生錯誤: {e}")

if __name__ == '__main__':
    main()
