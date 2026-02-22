
import psycopg2
import json

def check_schema():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    conn = psycopg2.connect(config['db']['url'])
    cur = conn.cursor()
    
    print("--- Portfolio Table Columns ---")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'portfolio';")
    for row in cur.fetchall():
        print(row)
        
    print("\n--- Transactions Table Columns ---")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'transactions';")
    for row in cur.fetchall():
        print(row)
    
    conn.close()

if __name__ == "__main__":
    check_schema()
