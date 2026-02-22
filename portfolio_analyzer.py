import psycopg2
import json
import pandas as pd
from datetime import datetime
import os

class PortfolioAnalyzer:
    def __init__(self):
        with open('config.json', 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            self.db_config = self.config['db']
        self.conn = psycopg2.connect(self.db_config['url'])
        # Exchange rate from CSV inspection (approximate)
        self.usd_krw = 1445.10 

    def get_portfolio(self):
        query = """
            SELECT ticker, name, quantity, avg_price, current_price, market_type, currency 
            FROM portfolio 
            ORDER BY (quantity * current_price) DESC;
        """
        return pd.read_sql(query, self.conn)

    def get_recent_transactions(self, days=90):
        query = """
            SELECT trade_date, ticker, type, quantity, price, market_type 
            FROM transactions 
            ORDER BY trade_date DESC 
            LIMIT 20;
        """
        # Note: 'days' not strictly used in query for now, just getting last 20
        return pd.read_sql(query, self.conn)

    def get_market_trends_for_holding(self, ticker):
        # Check if any investor trend exists for this ticker regardless of date (since data is recent snapshot)
        query = """
            SELECT date, investor_type, trade_type, quantity, amount, rank 
            FROM market_trends 
            WHERE ticker = %s 
            ORDER BY date DESC, rank ASC
        """
        return pd.read_sql(query, self.conn, params=(ticker,))

    def generate_report(self):
        df_port = self.get_portfolio()
        df_trans = self.get_recent_transactions()
        
        # 1. 자산 배분 분석
        total_krw = 0
        kr_val = 0
        us_val = 0
        
        holdings_analysis = []

        # 번역 매핑
        investor_map = {"INSTITUTION": "기관", "FOREIGN": "외국인"}
        trade_map = {"BUY": "매수", "SELL": "매도"}

        for _, row in df_port.iterrows():
            qty = row['quantity']
            price = row['current_price']
            
            val = qty * price
            if row['currency'] == 'USD':
                val_krw = val * self.usd_krw
                us_val += val_krw
            else:
                val_krw = val
                kr_val += val_krw
            
            total_krw += val_krw
            
            # 수급 트렌드 분석
            trends = self.get_market_trends_for_holding(row['ticker'])
            sentiment_summary = []
            if not trends.empty:
                for _, t in trends.iterrows():
                    inv_type = investor_map.get(t['investor_type'], t['investor_type'])
                    trd_type = trade_map.get(t['trade_type'], t['trade_type'])
                    sentiment_summary.append(f"{inv_type} {trd_type} {t['rank']}위")
            
            holdings_analysis.append({
                'ticker': row['ticker'],
                'name': row['name'],
                'val_krw': val_krw,
                'weight': 0, 
                'pnl_pct': ((row['current_price'] - row['avg_price']) / row['avg_price'] * 100) if row['avg_price'] > 0 else 0,
                'trends': ", ".join(sentiment_summary) if sentiment_summary else "-"
            })

        # 비중 계산
        if total_krw > 0:
            for h in holdings_analysis:
                h['weight'] = (h['val_krw'] / total_krw) * 100

        # 비중 순 정렬
        holdings_analysis.sort(key=lambda x: x['val_krw'], reverse=True)

        # 2. 마크다운 리포트 생성
        report = []
        report.append(f"# 📊 투자 전략 리포트 ({datetime.now().strftime('%Y-%m-%d')})")
        report.append("\n## 1. 포트폴리오 요약")
        report.append(f"- **총 자산(AUM)**: {total_krw:,.0f} KRW")
        if total_krw > 0:
            report.append(f"- **자산 구성**: 국내 {kr_val/total_krw*100:.1f}% | 미국 {us_val/total_krw*100:.1f}%")
        report.append(f"- **적용 환율 (USD/KRW)**: {self.usd_krw:,.2f}")

        report.append("\n### 주요 보유 종목 및 시장 수급 현황")
        report.append("| 티커 | 종목명 | 비중 | 수익률 | 기관/외국인 수급 상위 |")
        report.append("|---|---|---|---|---|")
        
        for h in holdings_analysis:
            # 센티널 알림 하이라이트
            trend_str = h['trends']
            if "매수" in trend_str: trend_str = f"**{trend_str}** 🟢"
            if "매도" in trend_str: trend_str = f"{trend_str} 🔴"
            
            pnl_str = f"{h['pnl_pct']:.2f}%"
            if h['pnl_pct'] > 0: pnl_str = f"+{pnl_str} 🔴" 
            else: pnl_str = f"{pnl_str} 🔵"

            report.append(f"| {h['ticker']} | {h['name']} | {h['weight']:.1f}% | {pnl_str} | {trend_str} |")

        report.append("\n## 2. 최근 매매 내역 (최근 20건)")
        report.append("| 일자 | 티커 | 구분 | 수량 | 가격 |")
        report.append("|---|---|---|---|---|")
        for _, row in df_trans.iterrows():
            report.append(f"| {row['trade_date']} | {row['ticker']} | {row['type']} | {row['quantity']} | {row['price']:,.2f} |")

        report.append("\n## 3. 센티널 전략 제언")
        report.append("> 보유 종목과 시장 수급(기관/외인 상위) 교차 분석 결과")
        
        opportunities = [h for h in holdings_analysis if "매수" in h['trends']]
        risks = [h for h in holdings_analysis if "매도" in h['trends']]
        
        if opportunities:
            report.append("\n### 🚀 추가 매수 및 긍정적 검토 (Confluence)")
            for h in opportunities:
                report.append(f"- **{h['name']} ({h['ticker']})**: 주요 세력의 집중 매수 포착. 현재 수익률: {h['pnl_pct']:.2f}%. 추세 지속 시 비중 확대 검토.")
        
        if risks:
            report.append("\n### ⚠️ 리스크 관리 및 주의 (Divergence)")
            for h in risks:
                report.append(f"- **{h['name']} ({h['ticker']})**: 주요 세력의 이탈/매도세 포착. 포지션 축소 및 리스크 관리 필요.")

        if not opportunities and not risks:
            report.append("\n- 현재 보유 종목 중 기관/외국인 매수/매도 상위 리스트에 중복되는 종목이 없습니다.")

        return "\n".join(report)

if __name__ == "__main__":
    analyzer = PortfolioAnalyzer()
    report_md = analyzer.generate_report()
    
    # Save to file
    with open("investment_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    
    print("Report generated: investment_report.md")
    print(report_md) # Print to stdout for verify
