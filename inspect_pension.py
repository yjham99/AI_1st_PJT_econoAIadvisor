import psycopg2
import json

def inspect():
    with open('config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)['db']
    conn = psycopg2.connect(cfg['url'])
    cur = conn.cursor()
    
    print("### Search content for '연금' ###")
    cur.execute("SELECT content FROM daily_market_analysis")
    for r in cur.fetchall():
        if '연금' in r[0]:
            print(r[0])
            
    print("\n### Search portfolio for Pension like items ###")
    cur.execute("SELECT * FROM portfolio")
    for r in cur.fetchall():
        print(r)
        
    conn.close()

if __name__ == '__main__':
    inspect()
