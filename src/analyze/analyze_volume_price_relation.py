import pandas as pd
import sqlite3

def analyze_volume_price_relation(stock_id, days=10):
    # 連線到資料庫並讀取資料
    conn = sqlite3.connect("data/institution.db")
    query = """
        SELECT date AS date, close AS close, volume AS volume
        FROM twse_prices
        WHERE stock_id = ?
        ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()

    df = df.sort_values(by='date').reset_index(drop=True)
    df = df[['date', 'close', 'volume']]
    df['prev_close'] = df['close'].shift(1)
    df['prev_volume'] = df['volume'].shift(1)

    df['price_up'] = df['close'] > df['prev_close']
    df['volume_up'] = df['volume'] > df['prev_volume']

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

    df_recent = df.tail(days).iloc[::-1].reset_index(drop=True)
    sync_count = df_recent['relation'].str.contains('同步').sum()
    diverge_count = df_recent['relation'].str.contains('背離').sum()

    print(f"\n📊 分析 {stock_id} 過去 {days} 天：")
    print(f"✅ 價量同步天數：{sync_count}")
    print(f"⚠️ 價量背離天數：{diverge_count}\n")
    print(df_recent[['date', 'close', 'volume', 'relation']].to_string(index=False))

    return df_recent

if __name__ == "__main__":
    analyze_volume_price_relation("2330", days=10)
