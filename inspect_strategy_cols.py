import psycopg2
import json
import pandas as pd

def inspect_columns():
    with open('config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)['db']
    conn = psycopg2.connect(cfg['url'])
    df = pd.read_sql("SELECT * FROM strategy_focus LIMIT 1", conn)
    print("Columns in strategy_focus:", df.columns.tolist())
    conn.close()

if __name__ == '__main__':
    inspect_columns()
