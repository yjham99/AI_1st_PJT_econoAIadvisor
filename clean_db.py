"""
DB 클린업 스크립트
- portfolio, transactions 테이블의 오염된 데이터 전체 삭제
- 더미 테스트 데이터 포함 전부 초기화
"""
import psycopg2
import json

def clean_db():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    conn = psycopg2.connect(config['db']['url'])
    cur = conn.cursor()
    
    try:
        # 1. transactions 전체 삭제
        cur.execute("DELETE FROM transactions;")
        trans_deleted = cur.rowcount
        print(f"[완료] transactions 삭제: {trans_deleted}건")
        
        # 2. portfolio 전체 삭제 (더미 + 오염 데이터 모두)
        cur.execute("DELETE FROM portfolio;")
        port_deleted = cur.rowcount
        print(f"[완료] portfolio 삭제: {port_deleted}건")
        
        conn.commit()
        print("\n✅ DB 클린업 완료. 깨끗한 상태에서 재시작 준비됨.")
        
        # 3. 현재 상태 확인
        cur.execute("SELECT COUNT(*) FROM portfolio;")
        print(f"   portfolio 잔여: {cur.fetchone()[0]}건")
        cur.execute("SELECT COUNT(*) FROM transactions;")
        print(f"   transactions 잔여: {cur.fetchone()[0]}건")
        
    except Exception as e:
        conn.rollback()
        print(f"[오류] 클린업 실패: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    clean_db()
