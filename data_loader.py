import os
import glob
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import json
import traceback
from datetime import datetime
import csv
import re

class BatchLoader:
    def __init__(self, base_dir=r"c:\AI_Study_Beginer\1st_PJT_econoAIadvisor"):
        self.base_dir = base_dir
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            self.db_config = config['db']
            # 지휘관 데스크탑 경로 (업무 기준 반영)
            cmd_path = config.get("paths", {}).get("commander_data", r"C:\Users\yjham\Desktop\경제 study")
            self.source_dirs = [self.base_dir, cmd_path]
    
    def get_connection(self):
        return psycopg2.connect(self.db_config['url'])

    def find_latest_file(self, pattern):
        all_files = []
        for d in self.source_dirs:
            if os.path.exists(d):
                all_files.extend(glob.glob(os.path.join(d, pattern)))
        
        if not all_files: return None
        # Sort by modification time to get the absolute latest across all dirs
        all_files.sort(key=os.path.getmtime, reverse=True)
        return all_files[0]

    def _clean_str(self, s):
        """ Remove quotes (' " =), strip whitespace """
        if pd.isna(s): return ""
        return str(s).replace("'", "").replace('"', "").replace('=', "").strip()

    def _read_csv(self, path, header=0):
        for enc in ['euc-kr', 'utf-8', 'cp949']:
            try:
                return pd.read_csv(path, encoding=enc, header=header)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(path, header=header)

    def _parse_number(self, s):
        """ Parse number string with commas """
        try:
            return float(self._clean_str(s).replace(',', ''))
        except:
            return 0.0

    def sync_portfolio_kr(self):
        f = self.find_latest_file("잔고_국내*.csv")
        if not f: return
        print(f"Syncing KR Portfolio from {f}...")
        
        try:
            df = self._read_csv(f)
            records = []
            for _, row in df.iterrows():
                # Columns: 종목코드, 종목명, 보유량, 매입가
                code = self._clean_str(row.get('종목코드'))
                name = self._clean_str(row.get('종목명'))
                if not code: continue
                
                # Ticker formatting
                if code.isdigit(): 
                    ticker = f"{code}.KS" # Default to KS, scanner will adjust or check
                else:
                    ticker = code
                
                qty = self._parse_number(row.get('보유량'))
                avg_price = self._parse_number(row.get('매입가'))
                cur_price = self._parse_number(row.get('현재가'))
                
                if qty > 0:
                    records.append((ticker, name, qty, avg_price, cur_price, 'KOSPI', 'KRW')) 
            
            self._upsert_portfolio(records)
            # Sync to master_stocks too
            master_records = [(r[0], r[1], r[5]) for r in records]
            self._upsert_master_stocks(master_records)
        except Exception:
            traceback.print_exc()

    def sync_portfolio_us(self):
        f = self.find_latest_file("잔고_미국*.csv")
        if not f: return
        print(f"Syncing US Portfolio from {f}...")
        
        try:
            # Check for header info
            with open(f, 'r', encoding='euc-kr', errors='ignore') as tf:
                first = tf.readline()
            
            header_row = 1 if 'Version=' in first else 0
            df = self._read_csv(f, header=header_row)
            
            records = []
            for _, row in df.iterrows():
                # Columns: 코드(or 종목코드), 보유량, 매입가
                code = self._clean_str(row.get('코드')) or self._clean_str(row.get('종목코드'))
                name = self._clean_str(row.get('종목명'))
                if not code: continue
                
                ticker = code
                qty = self._parse_number(row.get('보유량'))
                avg_price = self._parse_number(row.get('매입가')) 
                cur_price = self._parse_number(row.get('현재가'))
                
                if qty > 0:
                    records.append((ticker, name, qty, avg_price, cur_price, 'US', 'USD')) 
            
            self._upsert_portfolio(records)
            # Sync to master_stocks too
            master_records = [(r[0], r[1], r[5]) for r in records]
            self._upsert_master_stocks(master_records)
        except Exception:
            traceback.print_exc()

    def sync_pension(self):
        f = self.find_latest_file("연금_장기자산_*.csv")
        if not f: return
        print(f"Syncing Pension Assets from {f}...")
        try:
            df = self._read_csv(f)
            records = []
            for _, row in df.iterrows():
                name = self._clean_str(row.get('종목명'))
                if not name: continue
                
                # yield_str like "10.2%"
                yield_str = self._clean_str(row.get('수익률')).replace('%', '')
                yield_val = self._parse_number(yield_str)
                eval_amt = self._parse_number(row.get('평가금액'))
                
                # Estimate avg_price based on yield
                # current = avg * (1 + yield/100) -> avg = current / (1 + yield/100)
                avg_price = eval_amt / (1 + yield_val/100) if yield_val != -100 else eval_amt
                
                records.append((name, name, 1, avg_price, eval_amt, 'PENSION', 'KRW'))
            
            self._upsert_portfolio(records)
        except Exception:
            traceback.print_exc()

    def _upsert_portfolio(self, records):
        if not records: return
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            query = """
                INSERT INTO portfolio (ticker, name, quantity, avg_price, current_price, market_type, currency)
                VALUES %s
                ON CONFLICT (ticker) DO UPDATE 
                SET quantity = EXCLUDED.quantity, 
                    avg_price = EXCLUDED.avg_price,
                    current_price = EXCLUDED.current_price,
                    market_type = EXCLUDED.market_type, 
                    updated_at = CURRENT_TIMESTAMP;
            """
            execute_values(cur, query, records)
            conn.commit()
            print(f"Upserted {len(records)} records to portfolio.")
            cur.close()
        except Exception as e:
            print(f"DB Error in portfolio upsert: {e}")
            if conn: conn.rollback()
        finally:
            if conn: conn.close()

    def _upsert_master_stocks(self, records):
        """ records: List[(ticker, name, market_type)] """
        if not records: return
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            query = """
                INSERT INTO master_stocks (ticker, name, market_type)
                VALUES %s
                ON CONFLICT (ticker) DO UPDATE SET name = EXCLUDED.name, market_type = EXCLUDED.market_type, last_updated = CURRENT_TIMESTAMP;
            """
            execute_values(cur, query, records)
            conn.commit()
            cur.close()
        except:
            if conn: conn.rollback()
        finally:
            if conn: conn.close()

    def sync_transactions(self):
        # 1. KR Transactions
        f_kr = self.find_latest_file("거래내역*한국*.csv")
        if f_kr: 
            print(f"Loading KR Transactions from {f_kr}...")
            self._load_trans_kr(f_kr)

        # 2. US Transactions
        f_us = self.find_latest_file("거래내역*미국*.csv")
        if f_us: 
            print(f"Loading US Transactions from {f_us}...")
            self._load_trans_us(f_us)

    def _load_trans_kr(self, path):
        print(f"Loading KR Transactions from {os.path.basename(path)}...")
        records = []
        try:
            with open(path, 'r', encoding='euc-kr') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            start_idx = 0
            if "거래일자" in lines[0]: start_idx = 2 
            
            idx = start_idx
            while idx < len(lines) - 1:
                row1 = next(csv.reader([lines[idx]]))
                row2 = next(csv.reader([lines[idx+1]]))
                idx += 2
                
                try:
                    date_str = self._clean_str(row1[0]).replace('/', '-').replace('.', '-')
                    ticker = self._clean_str(row1[-1])
                    if ticker.isdigit(): ticker = f"{ticker}.KS"
                    
                    trade_type = "기타"
                    for col in row2:
                        c = self._clean_str(col)
                        if c and len(c) > 1 and not c.isdigit():
                            trade_type = c
                            break
                    
                    if not trade_type: trade_type = "Unknown"

                    qty = self._parse_number(row1[2])
                    price = self._parse_number(row1[3])
                    if price == 0: price = self._parse_number(row1[4])
                    
                    if not ticker: continue

                    records.append((ticker, date_str, trade_type, qty, price, 'KR', 'KRW'))
                except Exception:
                    continue
            
            self._upsert_transactions(records)
        except Exception:
            traceback.print_exc()

    def _load_trans_us(self, path):
        print(f"Loading US Transactions from {os.path.basename(path)}...")
        records = []
        try:
            with open(path, 'r', encoding='euc-kr') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            start_idx = 0
            if "Version" in lines[0]: start_idx = 4
            elif "거래일자" in lines[0]: start_idx = 3
            
            idx = start_idx
            while idx < len(lines) - 2:
                row1 = next(csv.reader([lines[idx]]))
                row2 = next(csv.reader([lines[idx+1]]))
                row3 = next(csv.reader([lines[idx+2]])) 
                idx += 3
                
                try:
                    date_str = self._clean_str(row1[0]).replace('/', '-').replace('.', '-')
                    ticker = self._clean_str(row2[0])
                    desc = self._clean_str(row2[1]) 
                    
                    qty = self._parse_number(row1[3])
                    price = self._parse_number(row2[2])
                    
                    type_r1 = self._clean_str(row1[1])
                    if type_r1 not in ['입출금', '']:
                        trade_type = f"{type_r1}-{desc}"
                    else:
                        trade_type = desc

                    records.append((ticker, date_str, trade_type, qty, price, 'US', 'USD'))
                except Exception:
                    continue
            
            self._upsert_transactions(records)
        except Exception:
            traceback.print_exc()

    def _upsert_transactions(self, records):
        if not records: return
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            query = """
                INSERT INTO transactions (ticker, trade_date, type, quantity, price, market_type, currency)
                VALUES %s
                ON CONFLICT (ticker, trade_date, type, quantity, price) DO NOTHING;
            """
            execute_values(cur, query, records)
            conn.commit()
            print(f"Inserted {len(records)} transactions.")
            cur.close()
        except Exception as e:
            print(f"DB Error in transactions: {e}")
            if conn: conn.rollback()
        finally:
            if conn: conn.close()

    def sync_market_trends(self):
        # 3. Market Trends (Institutional/Foreigner)
        trend_files = glob.glob(os.path.join(self.base_dir, "*기관*상위*.csv")) + \
                      glob.glob(os.path.join(self.base_dir, "*외국인*상위*.csv"))
        
        for f in trend_files:
            self._load_trend_file(f)

    def _load_trend_file(self, path):
        fname = os.path.basename(path)
        print(f"Loading Market Trend from {fname}...")
        
        # Determine metadata from filename
        investor = "INSTITUTION" if "기관" in fname else "FOREIGN"
        trade = "BUY" if "매수" in fname else "SELL"
        
        market = "KOSPI" 
        if "코스닥" in fname: market = "KOSDAQ"
        elif "외국인" in fname: market = "ALL" # Foreigner files often mix markets or implicit
        
        # Extract date range from filename if possible? 
        # Filename example: "260213 기관 매수상위(0209-0213) 코스피.csv"
        # Let's use the file modification date or extract '260213' (YYMMDD) prefix as the data date
        try:
            date_prefix = re.match(r"(\d{6})", fname).group(1)
            # 260213 -> 2026-02-13
            ref_date = datetime.strptime(date_prefix, "%y%m%d").date()
        except:
             # Fallback to today
             ref_date = datetime.now().date()

        try:
            df = self._read_csv(path)
            records = []
            
            for _, row in df.iterrows():
                code = self._clean_str(row.get('종목코드'))
                name = self._clean_str(row.get('종목명'))
                if not code: continue
                
                ticker = f"{code}.KS" if code.isdigit() else code # Simple heuristic
                if market == "KOSDAQ" and code.isdigit(): ticker = f"{code}.KQ"

                # Column names vary: '순매수수량(백주)', '순매도수량(백주)', '순매수량'
                qty_col = [c for c in df.columns if '수량' in c]
                amt_col = [c for c in df.columns if '금액' in c]
                
                qty = self._parse_number(row.get(qty_col[0])) if qty_col else 0
                amount = self._parse_number(row.get(amt_col[0])) if amt_col else 0
                
                # If SELL file, make sure quantities are positive for storage, 
                # or negative? Usually stored as absolute magnitude with 'SELL' type.
                # But in CSV '순매도수량' might be negative or positive.
                qty = abs(qty)
                amount = abs(amount)

                # Rank? implied by order? usually sorted.
                rank = _ + 1
                
                records.append((ref_date, ticker, name, market, investor, trade, qty, amount, rank))
            
            self._upsert_market_trends(records)
            # Sync to master_stocks too
            master_records = [(r[1], r[2], r[3]) for r in records]
            self._upsert_master_stocks(master_records)

        except Exception:
             traceback.print_exc()

    def _upsert_market_trends(self, records):
        if not records: return
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            query = """
                INSERT INTO market_trends (date, ticker, name, market_type, investor_type, trade_type, quantity, amount, rank)
                VALUES %s
                ON CONFLICT (date, ticker, investor_type, trade_type) 
                DO UPDATE SET quantity = EXCLUDED.quantity, amount = EXCLUDED.amount, rank = EXCLUDED.rank;
            """
            execute_values(cur, query, records)
            conn.commit()
            print(f"Upserted {len(records)} trends.")
            cur.close()
        except Exception as e:
            print(f"DB Error in trends: {e}")
            if conn: conn.rollback()
        finally:
            if conn: conn.close()

    def run(self):
        print("Starting Batch Data Load...")
        # 1. Portfolio
        self.sync_portfolio_kr()
        self.sync_portfolio_us()
        self.sync_pension()
        # 2. Transactions
        self.sync_transactions()
        # 3. Market Trends
        self.sync_market_trends()
        print("Batch Load Completed.")

if __name__ == "__main__":
    loader = BatchLoader()
    loader.run()
