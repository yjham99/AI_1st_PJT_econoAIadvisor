import psycopg2
import json

def get_lengths():
    with open('config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)['db']
    conn = psycopg2.connect(cfg['url'])
    cur = conn.cursor()
    cur.execute("SELECT column_name, character_maximum_length FROM information_schema.columns WHERE table_name = 'strategy_focus'")
    for row in cur.fetchall():
        print(f"{row[0]}: {row[1]}")
    conn.close()

if __name__ == '__main__':
    get_lengths()
