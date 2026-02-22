import psycopg2
import json
import pandas as pd

def inspect():
    with open('config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)['db']
    
    conn = psycopg2.connect(cfg['url'])
    
    print("\n### 1. Database Tables ###")
    tables = pd.read_sql("SELECT table_name FROM information_schema.tables WHERE table_schema='public'", conn)
    print(tables)
    
    for table in tables['table_name']:
        print(f"\n### Table: {table} (Row Count) ###")
        count = pd.read_sql(f"SELECT count(*) FROM {table}", conn)
        print(count)
        
        if table == 'portfolio':
             print(f"\n### Table: {table} (Content) ###")
             print(pd.read_sql(f"SELECT * FROM {table}", conn))

    print("\n### 2. Transaction Analysis for Lake Materials & Reinvestment ###")
    # Search for transactions related to Lake Materials or large cash flows
    trans = pd.read_sql("SELECT * FROM transactions ORDER BY trade_date DESC LIMIT 100", conn)
    print(trans)

    conn.close()

if __name__ == '__main__':
    inspect()
