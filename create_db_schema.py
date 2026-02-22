
import psycopg2
import json

def create_table():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        db_config = config['db']
        conn = psycopg2.connect(db_config['url'])
        cur = conn.cursor()
        
        # Drop tables to ensure fresh schema
        cur.execute("DROP TABLE IF EXISTS transactions;")
        cur.execute("DROP TABLE IF EXISTS portfolio;")
        cur.execute("DROP TABLE IF EXISTS market_trends;")

        # Create transactions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                trade_date DATE NOT NULL,
                type VARCHAR(50) NOT NULL,
                quantity NUMERIC(15, 4) DEFAULT 0,
                price NUMERIC(15, 2) DEFAULT 0,
                market_type VARCHAR(10),
                currency VARCHAR(5) DEFAULT 'KRW',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, trade_date, type, quantity, price)
            );
        """)

        # Create portfolio table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                ticker VARCHAR(20) PRIMARY KEY,
                name VARCHAR(100),
                quantity NUMERIC(15, 4) DEFAULT 0,
                avg_price NUMERIC(15, 2) DEFAULT 0,
                current_price NUMERIC(15, 2) DEFAULT 0,
                market_type VARCHAR(10),
                currency VARCHAR(5) DEFAULT 'KRW',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create market_trends table for Institutional/Foreigner flows
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_trends (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                ticker VARCHAR(20) NOT NULL,
                name VARCHAR(100),
                market_type VARCHAR(10),
                investor_type VARCHAR(20), -- INSTITUTION / FOREIGN
                trade_type VARCHAR(10), -- BUY / SELL
                quantity NUMERIC(15, 0),
                amount NUMERIC(20, 0), -- Transaction amount
                rank INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, ticker, investor_type, trade_type)
            );
        """)
        
        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_transactions_ticker ON transactions(ticker);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(trade_date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_market_trends_date ON market_trends(date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_market_trends_ticker ON market_trends(ticker);")
        
        conn.commit()
        print("Table 'transactions' created successfully.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error creating table: {e}")

if __name__ == "__main__":
    create_table()
