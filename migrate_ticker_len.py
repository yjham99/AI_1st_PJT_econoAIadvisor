
import psycopg2
import json

def migrate():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    conn = psycopg2.connect(config['db']['url'])
    cur = conn.cursor()
    
    print("Altering ticker column sizes...")
    cur.execute("ALTER TABLE portfolio ALTER COLUMN ticker TYPE VARCHAR(200);")
    cur.execute("ALTER TABLE transactions ALTER COLUMN ticker TYPE VARCHAR(200);")
    cur.execute("ALTER TABLE market_trends ALTER COLUMN ticker TYPE VARCHAR(200);")
    cur.execute("ALTER TABLE master_stocks ALTER COLUMN ticker TYPE VARCHAR(200);")
    
    # Also for watchlist just in case sentinel manager uses long names
    cur.execute("ALTER TABLE watchlist ALTER COLUMN ticker TYPE VARCHAR(200);")
    
    conn.commit()
    cur.close()
    conn.close()
    print("Migration completed.")

if __name__ == '__main__':
    migrate()
