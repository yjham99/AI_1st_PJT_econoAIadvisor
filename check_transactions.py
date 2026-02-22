
import psycopg2
import json

def check_trans():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    conn = psycopg2.connect(config['db']['url'])
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM transactions")
    cnt = cur.fetchone()[0]
    print(f"Transactions Count: {cnt}")
    
    cur.execute("SELECT * FROM transactions LIMIT 3")
    for r in cur.fetchall():
        print(r)
    conn.close()

if __name__ == "__main__":
    check_trans()
