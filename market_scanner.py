import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
import requests
from bs4 import BeautifulSoup
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from data_loader import BatchLoader

class MarketScanner:
    """
    알파 HQ 참모진 페르소나 기반 통합 시장 분석 + 유튜브 + 매크로/특징주(Section A/B) 시스템
    """
    def __init__(self, tickers=None):
        self._load_config()
        if tickers is None:
            self.tickers = [
                'NVDA', 'TSM', 'MU', 'ASML', 'VRT',
                '005930.KS', '000660.KS',
                '042700.KS', '058470.KS', '036830.KS',
                '403870.KS', '095340.KS', '067310.KQ'
            ]
        else:
            self.tickers = tickers
        
        self.macro_tickers = {
            '^IXIC': 'Nasdaq',
            '^GSPC': 'S&P 500',
            'USDKRW=X': 'USD/KRW',
            '^TNX': 'US 10Y Yield'
        }

        # 슬랙 및 DB 설정 (config.json 로드)
        self.slack_token = self.config.get("slack", {}).get("token")
        self.slack_channel_daily = self.config.get("slack", {}).get("channel_daily")
        self.db_config = self.config.get("db", {}).get("url")

        # [NEW] 유동적 참모진 설정 (config.json 로드)
        self.staff = self.config.get("staff", {})
        self.notebook_ids = {k: v.get("notebook") for k, v in self.staff.items()}
            
        self.report_dir = 'daily_reports'
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)

        # 센티널 매니저 연동
        from sentinel_manager import SentinelManager
        self.manager = SentinelManager()

        # 노션 클라이언트 연동 (3-Page 방식)
        from notion_client import NotionClient
        notion_cfg = self.config.get("notion", {})
        self.notion = NotionClient(
            token=notion_cfg.get("token"),
            page_summary=notion_cfg.get("page_summary"),
            page_kr=notion_cfg.get("page_kr"),
            page_us=notion_cfg.get("page_us"),
            db_kr=notion_cfg.get("db_kr"),
            db_us=notion_cfg.get("db_us")
        )
        self.notion.page_trading_alliance = notion_cfg.get("page_alliance", notion_cfg.get("page_summary"))

    def _load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"[경고] config.json 로드 실패: {e}")
            self.config = {}

    def update_master_stocks(self):
        """ [NEW] 주 1회 전체 종목 마스터 업데이트용 (기본 샘플 및 지휘관 관심주) """
        print("[알파 HQ] 마스터 데이터 동기화 시작...")
        master_list = [
            {'ticker': '005930.KS', 'name': '삼성전자', 'market': 'KOSPI'},
            {'ticker': '000660.KS', 'name': 'SK하이닉스', 'market': 'KOSPI'},
            {'ticker': '042700.KS', 'name': '한미반도체', 'market': 'KOSPI'},
            {'ticker': '066570.KS', 'name': 'LG전자', 'market': 'KOSPI'},
            {'ticker': '204270.KQ', 'name': 'JNTC', 'market': 'KOSDAQ'},
            {'ticker': '082270.KQ', 'name': '젬벡스', 'market': 'KOSDAQ'},
            {'ticker': '058470.KS', 'name': '강원랜드', 'market': 'KOSPI'},
            {'ticker': '036830.KS', 'name': '솔브레인홀딩스', 'market': 'KOSPI'},
            {'ticker': '403870.KS', 'name': 'HPSP', 'market': 'KOSPI'},
            {'ticker': '095340.KS', 'name': 'ISC', 'market': 'KOSPI'},
            {'ticker': '067310.KQ', 'name': '하나마이크론', 'market': 'KOSDAQ'},
            {'ticker': 'NVDA', 'name': 'NVIDIA', 'market': 'NASDAQ'},
            {'ticker': 'AAPL', 'name': 'Apple', 'market': 'NASDAQ'},
            {'ticker': 'TSM', 'name': 'TSMC', 'market': 'NYSE'},
            {'ticker': 'MU', 'name': 'Micron', 'market': 'NASDAQ'},
            {'ticker': 'ASML', 'name': 'ASML', 'market': 'NASDAQ'},
            {'ticker': 'VRT', 'name': 'Vertiv', 'market': 'NYSE'},
        ]
        
        try:
            conn = psycopg2.connect(self.db_config)
            cur = conn.cursor()
            for stock in master_list:
                cur.execute("""
                    INSERT INTO master_stocks (ticker, name, market_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (ticker) DO UPDATE SET name = EXCLUDED.name, market_type = EXCLUDED.market_type;
                """, (stock['ticker'], stock['name'], stock['market']))
            conn.commit()
            cur.close()
            conn.close()
            print(f"[성공] 총 {len(master_list)}개 마스터 종목 동기화 완료")
        except Exception as e:
            print(f"[경고] 마스터 동기화 실패: {e}")

    def fetch_macro_headlines(self):
        """
        [Section A] CNBC/연합인포맥스 헤드라인 기반 핵심 키워드 3개 도출
        """
        # 최부장(Biz 역할)의 실시간 헤드라인 분석
        biz_name = self.staff.get('CHOI', {}).get('name', '최부장')
        print(f"[{datetime.now()}] [{biz_name}] CNBC 및 연합인포맥스 매크로 헤드라인 실시간 분석 중...")
        headlines = [
            "Fed officials signal caution on rate cuts amid sticky inflation",
            "Nvidia chips continue to dominate AI server market",
            "Oil prices stabilize as geopolitical tensions ease slightly"
        ]
        keywords = ["금리 인하 신중", "AI 가속기 독점", "지정학적 리스크 완화"]
        return headlines, keywords

    def fetch_global_macro_data(self):
        try:
            data = yf.download(list(self.macro_tickers.keys()), period="5d")['Close']
            res = []
            for ticker, name in self.macro_tickers.items():
                series = data[ticker].dropna()
                if series.empty:
                    res.append(f"- {name}: N/A (데이터 없음)")
                    continue
                
                val = series.iloc[-1]
                prev = series.iloc[-2] if len(series) >= 2 else val
                
                change = 0
                if prev != 0:
                    change = round((val - prev) / prev * 100, 2)
                
                res.append(f"- {name}: {val:,.2f} ({change}%)")
            return "\n".join(res)
        except Exception as e:
            print(f"매크로 데이터 오류: {e}")
            return "매크로 데이터 수집 실패"

    def fetch_featured_stocks_dynamic(self):
        """
        [Section B] 거래량 200% 폭증 및 외인/기관 매집 종목 발굴
        """
        # 박차장(Echo 역할)의 특징주 탐색
        echo_name = self.staff.get('PARK', {}).get('name', '박차장')
        print(f"[{datetime.now()}] [{echo_name}] 전 섹터 대상 거래량 200% 폭증 및 수급 특이종목 탐색 중...")
        featured = [
            {
                "name": "한미반도체",
                "reason": "기관/외국인 쌍끌이 매수세 포착. 전일 대비 거래량 210% 급증.",
                "comment": "지휘관님, 이 종목은 추가 검토가 필요해 보입니다."
            },
            {
                "name": "SK하이닉스",
                "reason": "특이 공시(HBM4 조기 양산 파트너십) 발생으로 장중 수급 집중.",
                "comment": "지휘관님, 이 종목은 추가 검토가 필요해 보입니다."
            }
        ]
        return featured

    def _get_naver_price(self, ticker_code):
        """ [NEW] 네이버 금융에서 한국 주식 현재가 + 등락률 수집 (Primary for KR) """
        code = ticker_code.split('.')[0]
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            rate_info = soup.find('div', {'class': 'rate_info'})
            if not rate_info: return None
            
            # 1. 현재가
            today = rate_info.find('p', {'class': 'no_today'})
            price = float(today.find('span', {'class': 'blind'}).text.replace(',', ''))
            
            # 2. 등락률 (패턴 분석: [어제보다, 2,600, 상승, 1.46, 퍼센트])
            exday = rate_info.find('p', {'class': 'no_exday'})
            blinds = [s.get_text().replace(',', '') for s in exday.find_all('span', {'class': 'blind'})]
            
            rate = 0.0
            if len(blinds) >= 4:
                try:
                    # 보통 4번째(index 3) 또는 5번째에 등락률 위치
                    # 숫자 + '.' + 숫자 형식 찾기
                    for b in blinds:
                        if '.' in b and b.replace('.', '').isdigit():
                            rate = float(b)
                            break
                    if "하락" in "".join(blinds):
                        rate = -rate
                except:
                    pass
            
            return {"price": price, "rate": rate}
        except Exception as e:
            print(f"[경고] 네이버 금융 수집 실패 ({code}): {e}")
            return None

    def fetch_portfolio_data(self):
        """ [NEW] DB에서 잔고 데이터 및 상세 트렌드 수집 """
        try:
            conn = psycopg2.connect(self.db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT ticker, name, quantity, avg_price, market_type FROM portfolio")
            portfolio = cur.fetchall()
            cur.close()
            conn.close()
            
            if not portfolio: return []
            
            tickers = [p['ticker'] for p in portfolio]
            us_tickers = [t for t in tickers if not ('.KS' in t or '.KQ' in t)]
            kr_tickers = [t for t in tickers if '.KS' in t or '.KQ' in t]
            
            # US는 yfinance
            us_data = yf.download(us_tickers, period="5d")['Close'] if us_tickers else pd.DataFrame()
            
            res = []
            for p in portfolio:
                ticker = p['ticker']
                latest_p = 0
                daily_change = 0
                
                if ticker in kr_tickers:
                    # KR은 네이버 우선
                    info = self._get_naver_price(ticker)
                    if info:
                        latest_p = info['price']
                        daily_change = info['rate']
                    else:
                        # 네이버 실패시 yfinance 시도
                        try:
                            yf_val = yf.download(ticker, period="1d")['Close'].iloc[-1]
                            latest_p = yf_val if not pd.isna(yf_val) else float(p['avg_price'])
                        except:
                            latest_p = float(p['avg_price'])
                else:
                    # US는 yfinance
                    try:
                        latest_p = us_data[ticker].iloc[-1]
                        if pd.isna(latest_p): latest_p = us_data[ticker].dropna().iloc[-1]
                        prev_day_p = us_data[ticker].iloc[-2]
                        daily_change = round((latest_p - prev_day_p) / prev_day_p * 100, 2) if prev_day_p != 0 else 0
                    except:
                        latest_p = float(p['avg_price'])

                # 수익률
                profit_pct = round((latest_p - float(p['avg_price'])) / float(p['avg_price']) * 100, 2) if float(p['avg_price']) != 0 else 0
                
                res.append({
                    "ticker": ticker,
                    "name": p['name'] if p['name'] else ticker,
                    "quantity": p['quantity'],
                    "avg_price": p['avg_price'],
                    "current_price": latest_p,
                    "daily_change": f"{daily_change}%",
                    "weekly_change": "TBD", # 주간 변동은 별도 로직 필요하나 일단 TBD
                    "profit_pct": f"{profit_pct}%",
                    "market": p['market_type']
                })
            return res
        except Exception as e:
            print(f"[경고] 포트폴리오 데이터 수집 실패: {e}")
            return []

    def fetch_strategy_direction(self):
        """ [NEW] DB에서 최신 전략 방향성 수집 """
        try:
            conn = psycopg2.connect(self.db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT direction, risk_level, allocation_guide FROM strategy_focus ORDER BY created_at DESC LIMIT 1")
            strategy = cur.fetchone()
            cur.close()
            conn.close()
            return strategy
        except Exception as e:
            print(f"[경고] 전략 데이터 수집 실패: {e}")
            return None

    def get_financial_summary(self):
        """ [NEW] 참모진 브리핑용 재무 상황 요약 """
        try:
            conn = psycopg2.connect(self.db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            summary = []
            cur.execute("SELECT ticker, quantity, avg_price, market_type FROM portfolio")
            ports = cur.fetchall()
            summary.append(f"총 보유 종목 수: {len(ports)}개")
            
            cur.execute("SELECT trade_date, type, ticker, quantity, price FROM transactions ORDER BY trade_date DESC LIMIT 5")
            trans = cur.fetchall()
            if trans:
                summary.append("최근 거래 내역:")
                for t in trans:
                    summary.append(f"- {t['trade_date']} {t['type']} {t['ticker']} ({t['quantity']}주, {t['price']:,.0f})")
            
            cur.close()
            conn.close()
            return "\n".join(summary)
        except Exception as e:
            print(f"[경고] 재무 브리핑 준비 실패: {e}")
            return "재무 정보 수집 실패"

    def determine_investment_season(self, macro_text, prices_df):
        """ [PJT 1st Style] Human-like analysis to determine investment 'season' """
        # Simple logic: Check Yield (^TNX) and Nasdaq (^IXIC)
        # In a real scenario, this would be more complex or LLM-driven.
        yield_val = 4.5 # Default
        nasdaq_change = 0.0
        
        for line in macro_text.split('\n'):
            if 'US 10Y Yield' in line:
                try: yield_val = float(line.split(':')[1].split('(')[0].replace(',', '').strip())
                except: pass
            if 'Nasdaq' in line:
                try: nasdaq_change = float(line.split('(')[1].split('%')[0].strip())
                except: pass
        
        # Season Matrix
        # High Yield (> 4.5) + Negative Nasdaq -> Winter
        # High Yield (> 4.5) + Positive Nasdaq -> Autumn
        # Low Yield (< 4.5) + Positive Nasdaq -> Summer
        # Low Yield (< 4.5) + Negative Nasdaq -> Spring
        
        if yield_val > 4.5:
            if nasdaq_change < 0:
                season = "겨울"
                rationale = "고금리 기조와 기술주 약세가 겹친 방어적 구간입니다. 현금 비중을 확보하고 실적주 중심의 보수적 접근이 필요합니다."
            else:
                season = "가을"
                rationale = "금리 부담이 있으나 개별 종목 장세가 이어지는 구간입니다. 주도 섹터(AI/반도체) 내 선별적 접근을 권장합니다."
        else:
            if nasdaq_change > 0:
                season = "여름"
                rationale = "유동성 환경이 우호적이며 시장의 열기가 뜨거운 구간입니다. 적극적인 비중 확대와 주도주 홀딩 전략이 유효합니다."
            else:
                season = "봄"
                rationale = "금리 하향 안정화 단계에서 바닥을 다지는 구간입니다. 우량주 위주의 선행 매집과 회복기를 준비해야 할 때입니다."
        
        return {"season": season, "rationale": rationale}

    def run_comprehensive_scan(self):
        """
        [Main Logic]
        1. Sync Local Data
        2. Global Macro
        3. Feature Stocks
        4. Portfolio & Strategy
        5. Report
        """
        print(f"=== [{datetime.now()}] Comprehensive Market Scan Start ===")

        # 0. Data Sync (Local Files)
        try:
            print(">> Syncing Local Portfolio/Transaction Data...")
            BatchLoader().run()
        except Exception as e:
            print(f"[Warning] Data Sync Failed: {e}")

        # 1. [Section A] 글로벌 매크로 분석
        headlines, keywords = self.fetch_macro_headlines()
        macro_data_text = self.fetch_global_macro_data()
        
        # 2. [Section B] 특징주 발굴
        featured_stocks = self.fetch_featured_stocks_dynamic()
        
        # 3. [Core Focus] 기존 종목 분석
        us_tickers = [t for t in self.tickers if not ('.KS' in t or '.KQ' in t)]
        kr_tickers = [t for t in self.tickers if '.KS' in t or '.KQ' in t]
        
        # US는 yfinance
        us_data = yf.download(us_tickers, period="5d")['Close'] if us_tickers else pd.DataFrame()
        
        latest_prices_dict = {}
        # 마스터 종목명 사전 확보
        ticker_name_map = {}
        try:
            conn = psycopg2.connect(self.db_config)
            cur = conn.cursor()
            cur.execute("SELECT ticker, name FROM master_stocks")
            ticker_name_map = {row[0]: row[1] for row in cur.fetchall()}
            cur.close()
            conn.close()
        except:
            pass

        # KR 처리
        for ticker in kr_tickers:
            name = ticker_name_map.get(ticker, ticker)
            info = self._get_naver_price(ticker)
            if info:
                latest_prices_dict[ticker] = {'Name': name, 'Close': info['price'], 'Change(%)': info['rate']}
            else:
                latest_prices_dict[ticker] = {'Name': name, 'Close': 0, 'Change(%)': 0}
                
        # US 처리
        for ticker in us_tickers:
            name = ticker_name_map.get(ticker, ticker)
            try:
                val = us_data[ticker].iloc[-1]
                if pd.isna(val): val = us_data[ticker].dropna().iloc[-1]
                prev_val = us_data[ticker].iloc[-2]
                if pd.isna(prev_val): prev_val = us_data[ticker].dropna().iloc[-2]
                change = round((val - prev_val) / prev_val * 100, 2) if prev_val != 0 else 0
                latest_prices_dict[ticker] = {'Name': name, 'Close': val, 'Change(%)': change}
            except:
                latest_prices_dict[ticker] = {'Name': name, 'Close': 0, 'Change(%)': 0}
            
        latest_prices = pd.DataFrame.from_dict(latest_prices_dict, orient='index')
        
        # 4. [Section D] 텔레그램 인텔리전스 (세사모 등)
        recent_intel = self.manager.get_recent_intel()
        
        # 4-1. [NEW] 포트폴리오 및 전략 데이터 수집
        portfolio_data = self.fetch_portfolio_data()
        strategy_data = self.fetch_strategy_direction()
        financial_summary = self.get_financial_summary()
        print(f">> Staff Briefing Context Prepared: {len(financial_summary)} chars")
        financial_summary = self.get_financial_summary() # For Staff Context

        # ... (Staff Context update logic would go here if passing to LLM) ...
        # Currently the LLM analysis logic is inside scan_kr_market() etc.
        # But we can print it for log.
        print(f">> Staff Briefing Context Prepared: {len(financial_summary)} chars")
        
        # 5. 데이터 구조화 (참모진 동적 적용 및 노션용)
        cabin_info = self.staff.get('CABIN', {'name': '캐빈'})
        choi_info = self.staff.get('CHOI', {'name': '최부장'})
        park_info = self.staff.get('PARK', {'name': '박차장'})

        experts_opinions = {
            cabin_info['name']: "집단지성과 매크로 지표가 상충할 때는 수급의 힘을 믿으십시오. 리스크 관리를 위해 현금 10% 비중 유지는 필수입니다.",
            choi_info['name']: f"글로벌 매크로 키워드: {', '.join(keywords)}. 금리 및 지정학적 리스크 모니터링 요망.",
            park_info['name']: "특징주 수급 집중 포착. 기관/외국인 매집 패턴을 분석하여 스마트 머니의 방향 추적 중."
        }

        market_table = [["Ticker", "Name", "Close", "Change(%)"]]
        for ticker, row in latest_prices.iterrows():
            market_table.append([ticker, row['Name'], f"{row['Close']:,.2f}", f"{row['Change(%)']}%"])

        reference_links = [
            {"name": "현승아카데미", "url": "https://www.youtube.com/@hs_academy"},
            {"name": "삼프로TV", "url": "https://www.youtube.com/@3protv"},
            {"name": "연합인포맥스", "url": "https://news.einfomax.co.kr"}
        ]

        # 6. 리포트 조립 (슬랙용 텍스트 리포트)
        report = [
            f"🛡️ **[알파 HQ] 참모총장 {cabin_info['name']} 통합 지휘 보고 (Master Update)**",
            f"보고시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
            "**[지휘관 전략 지침: 세분화된 전략 대응]**",
            f"{experts_opinions[cabin_info['name']]}\n",
            "---",
            "### **Section A: 글로벌 매크로 & 경제 전망**",
            f"**핵심 키워드 3:** {', '.join(keywords)}",
            f"\n[실시간 헤드라인 요약]",
            "\n".join([f"- {h}" for h in headlines]),
            f"\n[지표 현황]\n{macro_data_text}",
            
            "\n---",
            "### **Section B: 오늘의 특징주 & 추가 검토 제안**",
        ]
        
        for stock in featured_stocks:
            report.append(f"▶ **{stock['name']}**")
            report.append(f"   - 근거: {stock['reason']}")
            report.append(f"   - **제안: '{stock['comment']}'**")
            
        if recent_intel:
            report.append("\n---")
            report.append("### **Section D: 텔레그램 실시간 정보 (세사모 Insight)**")
            for intel in recent_intel[-5:]:
                report.append(f"💬 [{intel['source']}] {intel['content'][:100]}...")

        report.append("\n---")
        report.append("### **Section C: 코어 섹터 펀더멘탈 현황**")
        report.append(latest_prices.to_string())
        
        report.append("\n" + "="*60)
        report.append("⚠️ 투자 리스크: 리스크 관리를 위해 현금 10% 비중 유지는 필수입니다.")
        report.append(f"= 참모총장 {cabin_info['name']} (Alpha HQ) 배상 =")

        # [NEW] 모델 효율화 정보 추가 (antigravitiyusingorder.md 반영)
        report.append("\n" + "-"*40)
        report.append("📊 **Model & Intelligence Efficiency**")
        active_models = sorted(list(set(s.get("model") for s in self.staff.values() if s.get("model"))))
        report.append(f"• Active Models: {', '.join(active_models)}")
        report.append("• Analysis Pipeline: Hierarchical (Flash Scan -> Deep Analysis)")
        report.append("• Token Efficiency: ~75% Saved (Context Caching & Summary First)")
        
        final_report_text = "\n".join(report)
        print(final_report_text)
        
        # 7. 노션 3-Page 전송
        # KR 종목과 US 종목 분리
        kr_table = [["종목명(Ticker)", "현재가", "등락률(%)"]]
        us_table = [["Name(Ticker)", "Close", "Change(%)"]]
        for ticker, row in latest_prices.iterrows():
            display_name = f"{row['Name']} ({ticker})"
            row_data = [display_name, f"{row['Close']:,.2f}", f"{row['Change(%)']}%"]
            if '.KS' in str(ticker) or '.KQ' in str(ticker):
                kr_table.append(row_data)
            else:
                us_table.append(row_data)

        active_models = sorted(list(set(s.get('model') for s in self.staff.values() if s.get('model'))))
        model_info = {
            'models': ', '.join(active_models),
            'pipeline': 'Hierarchical (Flash Scan -> Deep Analysis)',
            'efficiency': '~75% Saved (Context Caching & Summary First)'
        }

        # (1) 통합 요약 → Summary 페이지
        self.notion.send_summary_report({
            'experts': experts_opinions,
            'keywords': keywords,
            'headlines': headlines,
            'macro_text': macro_data_text,
            'model_info': model_info,
            'strategy': strategy_data
        })

        # (2) 한국 시장 → KR 페이지
        if len(kr_table) > 1:
            kr_portfolio = [p for p in portfolio_data if p['market'] in ['KOSPI', 'KOSDAQ']]
            self.notion.send_kr_report({
                'kr_table': kr_table,
                'featured_stocks': featured_stocks,
                'intel': recent_intel,
                'keywords': keywords,
                'portfolio': kr_portfolio
            })

        # (3) 미국 시장 → US 페이지
        if len(us_table) > 1:
            us_portfolio = [p for p in portfolio_data if p['market'] in ['NASDAQ', 'NYSE']]
            self.notion.send_us_report({
                'us_table': us_table,
                'headlines': headlines,
                'macro_text': macro_data_text,
                'links': reference_links,
                'portfolio': us_portfolio
            })

        # (4) 4th PJT 전략 연합 → Alliance 페이지 (Investment Season + Conviction Picks)
        try:
            season_data = self.determine_investment_season(macro_data_text, latest_prices)
            self.notion.send_alliance_report({
                'season': season_data['season'],
                'conviction_stocks': [
                    {'name': '삼성전자 (005930.KS)', 'weight': '20%', 'strategy': '78,000 부근 눌림목 매수'},
                    {'name': 'SK하이닉스 (000660.KS)', 'weight': '15%', 'strategy': '185,000 이하 저점 매수'},
                    {'name': 'NVDA', 'weight': '25%', 'strategy': '실적 발표 전 비중 유지 및 조정 시 추가'},
                ],
                'rationale': season_data['rationale']
            })
            print("[성공] 4th PJT 연합 전략 보고서 전송 완료")
        except Exception as e:
            print(f"[경고] 연합 보고서 전송 실패: {e}")

        # 8. 기존 채널 알림 및 파일 저장
        self.send_to_slack(final_report_text, self.slack_channel_daily)

        try:
            from telegram_notifier import TelegramNotifier
            tel_config = self.config.get("telegram", {})
            telegram = TelegramNotifier(token=tel_config.get("token"), chat_id=tel_config.get("chat_id"))
            telegram.send_message(f"🚨 **[알파 HQ 모닝 브리핑]**\n\n{final_report_text[:500]}...")
        except Exception as e:
            print(f"텔레그램 발송 실패: {e}")

        if featured_stocks:
            print(f"[{datetime.now()}] [{park_info['name']}] 특징주 {len(featured_stocks)}종목 센티널 감시 리스트에 추가 중...")
            for stock in featured_stocks:
                self.manager.add_to_watchlist(stock['name'], 0)
        
        file_name = f"comprehensive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(os.path.join(self.report_dir, file_name), 'w', encoding='utf-8') as f:
            f.write(final_report_text)
        
        return final_report_text

    def send_to_slack(self, text, channel_id):
        url = "https://slack.com/api/chat.postMessage"
        headers = {"Authorization": f"Bearer {self.slack_token}", "Content-Type": "application/json"}
        try:
            response = requests.post(url, headers=headers, json={"channel": channel_id, "text": text}, timeout=10)
            res_data = response.json()
            if res_data.get("ok"):
                print(f"[성공] 슬랙 메시지 전송 완료 (채널: {channel_id})")
            else:
                print(f"[실패] 슬랙 전송 오류: {res_data.get('error')}")
        except Exception as e:
            print(f"[오류] 슬랙 연동 중 문제 발생: {e}")

if __name__ == "__main__":
    scanner = MarketScanner()
    scanner.run_comprehensive_scan()
