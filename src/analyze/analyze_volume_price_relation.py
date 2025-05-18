import pandas as pd

def analyze_volume_price_relation(csv_path, days=10):
    df = pd.read_csv(csv_path)
    df.columns = [col.lower() for col in df.columns]  # 全小寫統一

    df = df.sort_values(by='date').reset_index(drop=True)
    df = df[['date', 'close', 'volume']]
    df['prev_close'] = df['close'].shift(1)
    df['prev_volume'] = df['volume'].shift(1)

    df['price_up'] = df['close'] > df['prev_close']
    df['volume_up'] = df['volume'] > df['prev_volume']

    # 判斷類型 + 註解
    def get_relation(row):
        if row['price_up'] and row['volume_up']:
            return '✅ 同步（價↑ 量↑）'
        elif not row['price_up'] and not row['volume_up']:
            return '🟢 同步（價↓ 量↓）'
        elif row['price_up'] and not row['volume_up']:
            return '⚠️ 背離（價↑ 量↓）'
        else:
            return '❌ 背離（價↓ 量↑）'


    df['relation'] = df.apply(get_relation, axis=1)

    # 取最近 N 天（由近到遠排序）
    df_recent = df.tail(days).iloc[::-1].reset_index(drop=True)

    # 統計同步與背離次數（避免 emoji 阻礙判斷）
    sync_count = df_recent['relation'].str.contains('同步').sum()
    diverge_count = df_recent['relation'].str.contains('背離').sum()


    print(f"\n📊 分析過去 {days} 天：")
    print(f"✅ 價量同步天數：{sync_count}")
    print(f"⚠️ 價量背離天數：{diverge_count}\n")
    print(df_recent[['date', 'close', 'volume', 'relation']].to_string(index=False))

    return df_recent


if __name__ == "__main__":
    csv_path = "data/2330_history.csv"
    analyze_volume_price_relation(csv_path, days=10)
