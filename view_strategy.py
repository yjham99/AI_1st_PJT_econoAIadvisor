import psycopg2
import json
import pandas as pd

def view():
    with open('config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)['db']
    conn = psycopg2.connect(cfg['url'])
    print("### Strategy Focus ###")
    print(pd.read_sql("SELECT * FROM strategy_focus", conn).to_string())
    
    print("\n### Daily Market Analysis ###")
    print(pd.read_sql("SELECT * FROM daily_market_analysis", conn).to_string())
    
    conn.close()

if __name__ == '__main__':
    view()
