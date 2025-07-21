import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import sqlite3
import plotly.graph_objects as go

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

import plotly.graph_objects as go

def plot_strong_days(df, strong_dates, stock_id="2330"):
    df['是否強勢日'] = df['日期'].isin(pd.to_datetime(strong_dates))
    plot_df = df.tail(10).copy()
    plot_df['日期顯示'] = plot_df['日期'].dt.strftime('%m/%d')

    fig = go.Figure()

    # 收盤價折線圖
    fig.add_trace(go.Scatter(
        x=plot_df['日期顯示'],
        y=plot_df['收盤價'],
        mode='lines+markers',
        name='收盤價',
        marker=dict(color='blue')
    ))

    # 強勢日標註
    strong_df = plot_df[plot_df['是否強勢日']]
    fig.add_trace(go.Scatter(
        x=strong_df['日期顯示'],
        y=strong_df['收盤價'],
        mode='markers',
        name='強勢日',
        marker=dict(color='red', size=12, symbol='circle-open'),
        text=["強勢日" for _ in range(len(strong_df))],
        hoverinfo='text+x+y'
    ))

    fig.update_layout(
        title=f"{stock_id} 近十交易日 強勢日視覺化",
        xaxis_title="日期",
        yaxis_title="收盤價",
        hovermode="x unified",
        margin=dict(t=60, b=80),
        annotations=[
            dict(
                text="強勢日: 扣抵日收高，當天價漲量增",
                xref="paper", yref="paper",
                x=0, y=-0.25, showarrow=False,
                font=dict(size=12)
            )
        ]
    )

    fig.show()



def main():
    stock_id = "2330"
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
    import plotly.io as pio
    pio.renderers.default = "browser"
    main()
