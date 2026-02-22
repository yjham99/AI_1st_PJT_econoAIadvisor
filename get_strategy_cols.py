import psycopg2
import json

def get_cols():
    with open('config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)['db']
    conn = psycopg2.connect(cfg['url'])
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'strategy_focus'")
    print("Columns:", [r[0] for r in cur.fetchall()])
    conn.close()

if __name__ == '__main__':
    get_cols()
