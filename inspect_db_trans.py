import psycopg2
import json

def inspect():
    with open('config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)['db']
    
    conn = psycopg2.connect(cfg['url'])
    cur = conn.cursor()
    
    print("### Recent Transactions (Real-time DB) ###")
    cur.execute("SELECT trade_date, ticker, type, quantity, price FROM transactions ORDER BY trade_date DESC LIMIT 50")
    for row in cur.fetchall():
        print(row)
    
    print("\n### Lake Materials Specific History ###")
    cur.execute("SELECT trade_date, ticker, type, quantity, price FROM transactions WHERE ticker LIKE '%281740%' ORDER BY trade_date DESC")
    for row in cur.fetchall():
        print(row)
        
    cur.close()
    conn.close()

if __name__ == '__main__':
    inspect()
