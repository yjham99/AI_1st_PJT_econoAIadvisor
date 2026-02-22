import psycopg2
import json
from datetime import datetime

def update_strategy():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    conn = psycopg2.connect(config['db']['url'])
    cur = conn.cursor()
    
    # 1. Update Strategy Focus
    # Note: We assume strategy_focus has columns (id, date, focus_area, detail, status, created_at) based on previous logs
    # I will insert a new row for the 2026-02-22 tactical shift
    new_direction = "반도체 대형주 중심 압축 및 코스닥150 즉시 정리"
    allocation_detail = """
    - [매도] KODEX 코스닥150: 기관 대량 이탈로 인한 전량 매도 및 현금화. 
    - [매수] 삼성전자, SK하이닉스: 기관/외인 10조 원 규모 집중 매입 포착. 눌림목 분할 매수.
    - [보유] 우리기술투자: 외국인 980억 수급 유입에 따른 기술적 반등 대기.
    - [익절] 레이크머티리얼즈: 잔량 84주 전고점 부근 분할 익절 준비.
    """
    
    try:
        cur.execute("""
            INSERT INTO strategy_focus (focus_date, direction, risk_level, allocation_guide, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (datetime.now().date(), new_direction, "Tactical Shift", allocation_detail, datetime.now()))
        print("Strategy Focus updated.")
    except Exception as e:
        print(f"Error updating strategy_focus: {e}")
        conn.rollback()

    # 2. Update Watchlist (Sentinel Manager Logic)
    # Add/Update targets for monitoring
    targets = [
        ('229200.KS', 'KODEX 코스닥150', 20000, 'EXIT_ALERT'), # Current ~18955, set target slightly above for bounce exit
        ('005930.KS', '삼성전자', 178000, 'BUY_DIP'),       # Current ~182100, wait for dip
        ('000660.KS', 'SK하이닉스', 850000, 'BUY_DIP')       # Current ~885000, wait for dip
    ]
    
    for ticker, name, price, note in targets:
        cur.execute("""
            INSERT INTO watchlist (ticker, name, target_price)
            VALUES (%s, %s, %s)
            ON CONFLICT (ticker) DO UPDATE SET target_price = EXCLUDED.target_price;
        """, (ticker, name, price))
        print(f"Watchlist updated: {name} ({ticker}) at {price}")

    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    update_strategy()
