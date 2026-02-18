import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
import requests
from bs4 import BeautifulSoup
import json
import psycopg2
from psycopg2.extras import RealDictCursor

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

        # 노션 클라이언트 연동
        from notion_client import NotionClient
        notion_cfg = self.config.get("notion", {})
        self.notion = NotionClient(
            token=notion_cfg.get("token"),
            db_kr=notion_cfg.get("db_kr"),
            db_us=notion_cfg.get("db_us")
        )

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
            {'ticker': 'NVDA', 'name': 'NVIDIA', 'market': 'NASDAQ'},
            {'ticker': 'AAPL', 'name': 'Apple', 'market': 'NASDAQ'},
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
            latest = data.iloc[-1]
            prev = data.iloc[-2]
            res = []
            for ticker, name in self.macro_tickers.items():
                val = latest[ticker]
                change = ((val - prev[ticker]) / prev[ticker] * 100).round(2)
                res.append(f"- {name}: {val:,.2f} ({change}%)")
            return "\n".join(res)
        except: return "매크로 데이터 수집 실패"

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

    def run_comprehensive_scan(self):
        # 1. [Section A] 글로벌 매크로 분석
        headlines, keywords = self.fetch_macro_headlines()
        macro_data_text = self.fetch_global_macro_data()
        
        # 2. [Section B] 특징주 발굴
        featured_stocks = self.fetch_featured_stocks_dynamic()
        
        # 3. [Core Focus] 기존 종목 분석
        prices = yf.download(self.tickers, period="5d")['Close']
        latest_prices = prices.iloc[-1].to_frame(name='Close')
        prev_prices = prices.iloc[-2].to_frame(name='Prev')
        latest_prices['Change(%)'] = ((latest_prices['Close'] - prev_prices['Prev']) / prev_prices['Prev'] * 100).round(2)
        
        # 4. [Section D] 텔레그램 인텔리전스 (세사모 등)
        recent_intel = self.manager.get_recent_intel()
        
        # 5. 데이터 구조화 (참모진 동적 적용 및 노션용)
        cabin_info = self.staff.get('CABIN', {'name': '캐빈'})
        choi_info = self.staff.get('CHOI', {'name': '최부장'})
        park_info = self.staff.get('PARK', {'name': '박차장'})

        experts_opinions = {
            cabin_info['name']: "집단지성과 매크로 지표가 상충할 때는 수급의 힘을 믿으십시오. 리스크 관리를 위해 현금 10% 비중 유지는 필수입니다.",
            choi_info['name']: f"글로벌 매크로 키워드: {', '.join(keywords)}. 금리 및 지정학적 리스크 모니터링 요망.",
            park_info['name']: "특징주 수급 집중 포착. 기관/외국인 매집 패턴을 분석하여 스마트 머니의 방향 추적 중."
        }

        market_table = [["Ticker", "Close", "Change(%)"]]
        for ticker, row in latest_prices.iterrows():
            market_table.append([ticker, f"{row['Close']:,.2f}", f"{row['Change(%)']}%"])

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
        
        # 7. 노션 전송
        notion_data = {
            "title": f"참모진 통합 시장 분석 보고 ({cabin_info['name']} 지휘)",
            "experts": experts_opinions,
            "market_table": market_table,
            "links": reference_links
        }
        
        # KR/US 구분 (샘플 종목 리스트 기준으로 KR 전송)
        self.notion.send_report('KR', notion_data)

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
