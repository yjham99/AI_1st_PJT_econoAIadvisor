import json
import os
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    print("[참고] psycopg2 모듈이 없어 DB 연동이 비활성화됩니다. (JSON 모드 가동)")

from datetime import datetime

class SentinelManager:
    """
    [알파 HQ] 데이터 관리 매니저
    JSON(로컬)과 PostgreSQL(중앙) 통합 관리 및 업데이트 주기 고도화 지원
    """
    def __init__(self, file_path="watchlist.json"):
        self.file_path = file_path
        self._load_config()
        self._init_db()
        
        if not os.path.exists(self.file_path):
            self.save_data({"watchlist": [], "logs": [], "insights": [], "intel": []})

    def _load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                self.db_url = config.get("db", {}).get("url", "postgresql://postgres:0712@localhost:5432/econo_db")
        except:
            self.db_url = "postgresql://postgres:0712@localhost:5432/econo_db"

    def _init_db(self):
        """ DB 테이블 생성 로직 (PostgreSQL 전용) """
        if not HAS_PSYCOPG2:
            return

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            # 1. 마스터 종목 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS master_stocks (
                    ticker VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    market_type VARCHAR(20),
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 2. 감시 리스트 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(100),
                    target_price INTEGER DEFAULT 0,
                    current_price INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 3. 실시간 인텔리전스 로그
            cur.execute("""
                CREATE TABLE IF NOT EXISTS intelligence_logs (
                    id SERIAL PRIMARY KEY,
                    source VARCHAR(50),
                    content TEXT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            print("[성공] PostgreSQL 인프라 연동 및 테이블 점검 완료")
        except Exception as e:
            print(f"[경고] DB 연동 실패 (JSON 모드로 동작): {e}")

    def load_data(self):
        """ JSON 데이터 로드 (하위 호환성 유지) """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "insights" not in data: data["insights"] = []
                if "intel" not in data: data["intel"] = []
                return data
        except:
            return {"watchlist": [], "logs": [], "insights": [], "intel": []}

    def save_data(self, data):
        """ JSON 데이터 저장 """
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def add_to_watchlist(self, ticker_name, target_price):
        """ 종목 추가 (JSON + DB 동시 기록) """
        # 1. JSON 저장
        data = self.load_data()
        updated = False
        for item in data["watchlist"]:
            if item["name"] == ticker_name:
                item["target_price"] = target_price
                updated = True
                break
        
        if not updated:
            data["watchlist"].append({"name": ticker_name, "target_price": target_price})
        
        self.save_data(data)

        if not HAS_PSYCOPG2:
            return f"[{ticker_name}]을(를) {target_price}원에 감시 리스트(JSON)에 추가/업데이트했습니다."

        # 2. DB 저장
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO watchlist (ticker, name, target_price)
                VALUES (%s, %s, %s)
                ON CONFLICT (ticker) DO UPDATE SET target_price = EXCLUDED.target_price;
            """, (ticker_name, ticker_name, target_price))
            conn.commit()
            cur.close()
            conn.close()
        except:
            pass

        return f"[{ticker_name}]을(를) {target_price}원에 감시 리스트에 추가/업데이트했습니다."

    def remove_from_watchlist(self, ticker_name):
        """ 종목 삭제 (JSON + DB 동시 삭제) """
        # 1. JSON 삭제
        data = self.load_data()
        data["watchlist"] = [item for item in data["watchlist"] if item["name"] != ticker_name]
        self.save_data(data)

        # 2. DB 삭제
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("DELETE FROM watchlist WHERE name = %s OR ticker = %s", (ticker_name, ticker_name))
            conn.commit()
            cur.close()
            conn.close()
        except:
            pass
        
        return f"[{ticker_name}]을(를) 감시 리스트에서 삭제했습니다."

    def clear_watchlist(self):
        """ 감시 리스트 전체 초기화 (JSON + DB) """
        # 1. JSON 초기화
        data = self.load_data()
        data["watchlist"] = []
        self.save_data(data)

        # 2. DB 초기화
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("DELETE FROM watchlist")
            conn.commit()
            cur.close()
            conn.close()
        except:
            pass
        
        return "🧹 모든 감시 종목을 삭제하고 리스트를 초기화했습니다."

    def update_stock_price(self, ticker_name, price):
        """ 종목의 현재가 업데이트 (JSON + DB) """
        # 1. JSON 업데이트
        data = self.load_data()
        for item in data.get("watchlist", []):
            if item["name"] == ticker_name:
                item["current_price"] = price
                break
        self.save_data(data)

        # 2. DB 업데이트
        if HAS_PSYCOPG2:
            try:
                conn = psycopg2.connect(self.db_url)
                cur = conn.cursor()
                cur.execute("""
                    UPDATE watchlist SET current_price = %s WHERE name = %s OR ticker = %s
                """, (price, ticker_name, ticker_name))
                conn.commit()
                cur.close()
                conn.close()
            except:
                pass

    def get_watchlist(self):
        """ 감시 리스트 조회 (DB + JSON 통합 및 중복 제거) """
        watchlist_dict = {}
        
        # 1. JSON 데이터 먼저 로드
        for item in self.load_data().get("watchlist", []):
            name = item["name"]
            watchlist_dict[name] = item

        # 2. DB 데이터 로드 및 병합
        if HAS_PSYCOPG2:
            try:
                conn = psycopg2.connect(self.db_url)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT name, target_price, current_price FROM watchlist")
                rows = cur.fetchall()
                cur.close()
                conn.close()
                for row in rows:
                    name = row["name"]
                    watchlist_dict[name] = {
                        "name": name, 
                        "target_price": row["target_price"],
                        "current_price": row.get("current_price", 0)
                    }
            except:
                pass
        
        return list(watchlist_dict.values())

    def log_intel(self, source, content):
        """ 인텔리전스 누적 (JSON + DB) """
        # 1. JSON
        data = self.load_data()
        data["intel"].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "content": content
        })
        self.save_data(data)

        # 2. DB
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("INSERT INTO intelligence_logs (source, content) VALUES (%s, %s)", (source, content))
            conn.commit()
            cur.close()
            conn.close()
        except:
            pass

    def get_recent_intel(self):
        """ 최근 인텔리전스 조회 """
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT source, content, recorded_at as time FROM intelligence_logs ORDER BY recorded_at DESC LIMIT 10")
            rows = cur.fetchall()
            # 시간 포맷팅
            for row in rows:
                row['time'] = row['time'].strftime("%Y-%m-%d %H:%M:%S")
            cur.close()
            conn.close()
            if rows: return rows
        except:
            pass
        return self.load_data().get("intel", [])

    def find_ticker(self, name):
        """ 종목명으로 티커 검색 (DB -> 기본 매핑) """
        name_clean = name.strip().lower()
        
        # 1. DB 검색 (대소문자 무시)
        if HAS_PSYCOPG2:
            try:
                conn = psycopg2.connect(self.db_url)
                cur = conn.cursor()
                cur.execute("SELECT ticker FROM master_stocks WHERE LOWER(name) = %s", (name_clean,))
                row = cur.fetchone()
                cur.close()
                conn.close()
                if row: return row[0]
            except:
                pass

        # 2. 기본 매핑 (확장)
        ticker_map = {
            "삼성전자": "005930.KS",
            "sk하이닉스": "000660.KS",
            "sk하이닉스": "000660.KS",
            "한미반도체": "042700.KS",
            "lg전자": "066570.KS",
            "대덕전자": "008060.KS",
            "jntc": "204270.KQ",
            "젬벡스": "082270.KQ",
        }
        
        # 한국어 이름은 그대로, 영문은 소문자로 매핑 체크
        for k, v in ticker_map.items():
            if k.lower() == name_clean:
                return v
        return None
