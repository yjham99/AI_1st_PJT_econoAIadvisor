import requests
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NotionClient:
    """
    [알파 HQ] 노션 연동 클라이언트
    페이지 하위 블록 추가 방식으로 시장 분석 보고서를 저장
    - page_summary: 통합 요약 (미국+한국)
    - page_kr: 한국 시장 전용
    - page_us: 미국 시장 전용
    """
    def __init__(self, token, page_summary=None, page_kr=None, page_us=None, db_kr=None, db_us=None):
        self.token = token
        self.page_summary = page_summary
        self.page_kr = page_kr
        self.page_us = page_us
        self.db_kr = db_kr
        self.db_us = db_us
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def _sanitize(self, text):
        """Notion API에서 거부하는 특수문자/NaN 제거"""
        if not isinstance(text, str):
            text = str(text)
        text = text.replace("nan", "N/A").replace("NaN", "N/A")
        text = text.replace("inf", "∞").replace("-inf", "-∞")
        # 2000자 제한 (Notion rich_text 블록 제한)
        return text[:2000]

    # ─── 블록 빌더 (공통) ─────────────────────────────────────

    def _text_block(self, content, bold=False, italic=False, color="default"):
        return {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{
                "type": "text", "text": {"content": self._sanitize(content)},
                "annotations": {"bold": bold, "italic": italic, "color": color}
            }]}
        }

    def _heading(self, level, text):
        key = f"heading_{level}"
        return {"object": "block", "type": key, key: {
            "rich_text": [{"type": "text", "text": {"content": self._sanitize(text)}}]
        }}

    def _callout(self, icon, text, color="default"):
        return {
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": self._sanitize(text)}}],
                "icon": {"emoji": icon}, "color": color
            }
        }

    def _divider(self):
        return {"object": "block", "type": "divider", "divider": {}}

    def _bullet(self, text):
        return {
            "object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": self._sanitize(text)}}]
            }
        }

    def _table(self, rows_data):
        """rows_data: List[List[str]], 첫번째 행은 헤더"""
        table_rows = []
        for row in rows_data:
            cells = [[{"type": "text", "text": {"content": str(c)}}] for c in row]
            table_rows.append({
                "object": "block", "type": "table_row",
                "table_row": {"cells": cells}
            })
        return {
            "object": "block", "type": "table",
            "table": {
                "table_width": len(rows_data[0]),
                "has_column_header": True, "has_row_header": False,
                "children": table_rows
            }
        }

    def _toggle(self, title, children_blocks):
        """토글 블록 (접을 수 있는 섹션)"""
        return {
            "object": "block", "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": title}}],
                "children": children_blocks
            }
        }

    # ─── 공통 API ────────────────────────────────────────────

    def _append_blocks(self, page_id, blocks):
        """페이지에 child blocks 추가 (Notion API: PATCH /blocks/{id}/children)"""
        if not page_id:
            logger.warning("Page ID가 설정되지 않았습니다.")
            return False

        url = f"https://api.notion.com/v1/blocks/{page_id}/children"

        # Notion API는 한 번에 최대 100개 블록만 허용
        chunk_size = 100
        for i in range(0, len(blocks), chunk_size):
            chunk = blocks[i:i + chunk_size]
            try:
                # JSON 직렬화 검증
                payload = {"children": chunk}
                json.dumps(payload, ensure_ascii=False)  # 직렬화 테스트
                
                response = requests.patch(url, headers=self.headers,
                                          json=payload, timeout=30)
                if response.status_code == 200:
                    logger.info(f"블록 {i+1}~{i+len(chunk)} 추가 성공 (page: ...{page_id[-8:]})")
                else:
                    err = response.json()
                    logger.error(f"Notion 블록 추가 실패 ({response.status_code}): {err.get('message', response.text[:300])}")
                    return False
            except json.JSONDecodeError as e:
                logger.error(f"JSON 직렬화 오류 (블록 {i+1}~{i+len(chunk)}): {e}")
                return False
            except Exception as e:
                logger.error(f"Notion 연결 오류: {e}")
                return False

        return True

    # ─── 통합 요약 보고서 (Summary Page) ─────────────────────

    def send_summary_report(self, report_data):
        """
        통합 요약 보고서 → page_summary에 전송
        report_data: dict with keys: title, experts, keywords, headlines,
                     macro_text, kr_table, us_table, model_info
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        blocks = []

        # 날짜 헤딩
        blocks.append(self._heading(2, f"📅 {now} 통합 시장 브리핑"))
        blocks.append(self._divider())

        # 참모진 통합 의견
        blocks.append(self._heading(3, "🎙️ 참모진 통합 의견"))
        experts = report_data.get("experts", {})
        for name, opinion in experts.items():
            icon = "🐋" if any(x in name.upper() for x in ["CABIN", "캐빈", "총장"]) else "📈"
            blocks.append(self._callout(icon, f"{name}: {opinion}"))

        blocks.append(self._divider())

        # 매크로 키워드 & 헤드라인
        keywords = report_data.get("keywords", [])
        headlines = report_data.get("headlines", [])
        if keywords:
            blocks.append(self._heading(3, "🔑 핵심 키워드"))
            blocks.append(self._text_block(", ".join(keywords), bold=True))
        if headlines:
            blocks.append(self._heading(3, "📰 글로벌 헤드라인"))
            for h in headlines:
                blocks.append(self._bullet(h))

        blocks.append(self._divider())

        # 매크로 지표 요약
        macro_text = report_data.get("macro_text", "")
        if macro_text:
            blocks.append(self._heading(3, "📊 매크로 지표 현황"))
            for line in macro_text.strip().split("\n"):
                if line.strip():
                    blocks.append(self._bullet(line.strip().lstrip("- ")))

        blocks.append(self._divider())

        # [NEW] 전략 방향성 테이블
        strategy = report_data.get("strategy")
        if strategy:
            blocks.append(self._heading(3, "🎯 투자 전략 및 방향성 점검"))
            strat_table = [
                ["구분", "내용"],
                ["핵심 방향", strategy.get("direction", "N/A")],
                ["리스크 수준", strategy.get("risk_level", "N/A")],
                ["운영 가이드", strategy.get("allocation_guide", "N/A")]
            ]
            blocks.append(self._table(strat_table))
            blocks.append(self._divider())

        # 모델 효율화 정보
        model_info = report_data.get("model_info", {})
        if model_info:
            blocks.append(self._heading(3, "⚙️ Intelligence Efficiency"))
            blocks.append(self._bullet(f"Active Models: {model_info.get('models', 'N/A')}"))
            blocks.append(self._bullet(f"Pipeline: {model_info.get('pipeline', 'Hierarchical')}"))
            blocks.append(self._bullet(f"Token Efficiency: {model_info.get('efficiency', '~75%')}"))

        # 리스크 고지
        blocks.append(self._divider())
        blocks.append(self._callout("⚠️",
            "본 보고서는 정보 제공을 목적으로 하며, 투자 결정에 대한 최종 책임은 본인에게 있습니다.",
            "red_background"))

        return self._append_blocks(self.page_summary, blocks)

    # ─── 한국 시장 보고서 (KR Page) ──────────────────────────

    def send_kr_report(self, report_data):
        """
        한국 시장 보고서 → page_kr에 전송
        report_data: dict with keys: kr_table, featured_stocks, intel, keywords
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        blocks = []

        blocks.append(self._heading(2, f"🇰🇷 {now} 한국 시장 분석"))
        blocks.append(self._divider())

        # 핵심 키워드
        keywords = report_data.get("keywords", [])
        if keywords:
            blocks.append(self._callout("🔑", f"핵심 키워드: {', '.join(keywords)}"))

        # [NEW] KR 포트폴리오 & 트렌드
        portfolio = report_data.get("portfolio", [])
        if portfolio:
            blocks.append(self._heading(3, "💰 보유 잔고 트렌드 (Portfolio)"))
            port_table = [["종목명(Ticker)", "보유량", "매수단가", "현재가", "주간변동", "수익률"]]
            for p in portfolio:
                display_name = f"{p['name']} ({p['ticker']})"
                port_table.append([
                    display_name, str(p['quantity']), f"{p['avg_price']:,.0f}",
                    f"{p['current_price']:,.0f}", p['weekly_change'], p['profit_pct']
                ])
            blocks.append(self._table(port_table))
            blocks.append(self._divider())

        # KR 종목 데이터 테이블
        kr_table = report_data.get("kr_table", [])
        if kr_table:
            blocks.append(self._heading(3, "📊 코어 섹터 현황 (KOSPI/KOSDAQ)"))
            blocks.append(self._table(kr_table))

        blocks.append(self._divider())

        # 특징주
        featured = report_data.get("featured_stocks", [])
        if featured:
            blocks.append(self._heading(3, "🔥 오늘의 특징주"))
            for stock in featured:
                blocks.append(self._callout("📌",
                    f"{stock['name']}\n• 근거: {stock['reason']}\n• 제안: {stock.get('comment', '')}"))

        blocks.append(self._divider())

        # 텔레그램 인텔리전스
        intel = report_data.get("intel", [])
        if intel:
            blocks.append(self._heading(3, "💬 실시간 인텔리전스 (세사모 등)"))
            for item in intel[-5:]:
                blocks.append(self._bullet(f"[{item.get('source', '?')}] {item.get('content', '')[:150]}"))

        # 리스크
        blocks.append(self._divider())
        blocks.append(self._callout("⚠️",
            "투자 리스크: 리스크 관리를 위해 현금 10% 비중 유지는 필수입니다.", "red_background"))

        return self._append_blocks(self.page_kr, blocks)

    # ─── 미국 시장 보고서 (US Page) ──────────────────────────

    def send_us_report(self, report_data):
        """
        미국 시장 보고서 → page_us에 전송
        report_data: dict with keys: us_table, headlines, macro_text
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        blocks = []

        blocks.append(self._heading(2, f"🇺🇸 {now} 미국 시장 분석"))
        blocks.append(self._divider())

        # 매크로 헤드라인
        headlines = report_data.get("headlines", [])
        if headlines:
            blocks.append(self._heading(3, "📰 CNBC/Bloomberg 헤드라인"))
            for h in headlines:
                blocks.append(self._bullet(h))

        blocks.append(self._divider())

        # [NEW] US 포트폴리오 & 트렌드
        portfolio = report_data.get("portfolio", [])
        if portfolio:
            blocks.append(self._heading(3, "💰 US Portfolio Trends"))
            port_table = [["Name(Ticker)", "Qty", "Avg Cost", "Price", "Weekly", "ROI"]]
            for p in portfolio:
                display_name = f"{p['name']} ({p['ticker']})"
                port_table.append([
                    display_name, str(p['quantity']), f"{p['avg_price']:,.2f}",
                    f"{p['current_price']:,.2f}", p['weekly_change'], p['profit_pct']
                ])
            blocks.append(self._table(port_table))
            blocks.append(self._divider())

        # 매크로 지표
        macro_text = report_data.get("macro_text", "")
        if macro_text:
            blocks.append(self._heading(3, "📊 매크로 지표"))
            for line in macro_text.strip().split("\n"):
                if line.strip():
                    blocks.append(self._bullet(line.strip().lstrip("- ")))

        blocks.append(self._divider())

        # US 종목 테이블
        us_table = report_data.get("us_table", [])
        if us_table:
            blocks.append(self._heading(3, "📈 빅테크/반도체 핵심 종목"))
            blocks.append(self._table(us_table))

        # 참고 자료
        links = report_data.get("links", [])
        if links:
            blocks.append(self._divider())
            blocks.append(self._heading(3, "🔗 참고 자료"))
            for link in links:
                blocks.append(self._bullet(f"{link['name']}: {link['url']}"))

        # 리스크
        blocks.append(self._divider())
        blocks.append(self._callout("⚠️",
            "본 데이터는 참고용이며, 매매 결과에 대한 책임은 투자자 본인에게 귀속됩니다.", "red_background"))

        return self._append_blocks(self.page_us, blocks)

    # ─── 4th PJT 연합 보고서 (Trading Alliance) ──────────

    def send_alliance_report(self, report_data):
        """
        4th PJT (자동 투자 AI) 전용 전략 보드에 전송
        report_data: { 'season': '...', 'conviction_stocks': [...], 'rationale': '...' }
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        blocks = []

        blocks.append(self._heading(2, f"🤖 [PJT 1st] 전략 제언 (For 4th Trading AI)"))
        blocks.append(self._divider())

        # 1. 투자 계절 (Investment Season)
        season = report_data.get("season", "N/A")
        season_icon = {"봄": "🌱", "여름": "☀️", "가을": "🍂", "겨울": "❄️"}.get(season, "⚖️")
        blocks.append(self._heading(3, f"{season_icon} 현재 투자 계절: {season}"))
        
        # 2. 추천 종목 (Conviction Picks)
        blocks.append(self._heading(3, "🎯 전략적 핵심 추천 종목"))
        picks = report_data.get("conviction_stocks", [])
        pick_table = [["종목명(Ticker)", "권장 비중", "진입 전략"]]
        for p in picks:
            pick_table.append([p['name'], p['weight'], p['strategy']])
        blocks.append(self._table(pick_table))

        # 3. 상세 사유 (Rationale - 1st PJT's Human-like Analysis)
        blocks.append(self._heading(3, "📖 1st PJT 전략적 분석 사유 (Strategic Rationale)"))
        blocks.append(self._callout("🧠", report_data.get("rationale", "분석 사유가 입력되지 않았습니다.")))

        blocks.append(self._divider())
        blocks.append(self._text_block(f"※ 본 의견은 1st PJT(경제분석)의 관점이며, 4th PJT는 6th PJT(지표기반)의 의견과 교차 검증하여 최종 타이밍을 결정하십시오.", italic=True))

        # page_trading_alliance가 없으면 page_summary를 백업으로 사용하거나 리턴
        target_page = getattr(self, "page_trading_alliance", self.page_summary)
        return self._append_blocks(target_page, blocks)

    # ─── 레거시 호환 (Database 방식) ─────────────────────────

    def send_report(self, market_type, report_data):
        """기존 Database 기반 보고서 전송 (하위 호환)"""
        db_id = self.db_kr if market_type == 'KR' else self.db_us
        if not db_id or "ENTER_" in db_id:
            logger.warning(f"Notion Database ID for {market_type} is not set. Skipping DB report.")
            return False

        url = "https://api.notion.com/v1/pages"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        page_title = f"🛡️ [{market_type}] {report_data.get('title', '시장 통합 보고서')} ({current_time})"

        children = []
        children.append(self._heading(2, "🎙️ 참모진 통합 의견 (Expert Sync)"))
        experts = report_data.get('experts', {})
        for name, opinion in experts.items():
            icon = "🐋" if any(x in name.upper() for x in ["CABIN", "캐빈", "총장"]) else "📈"
            children.append(self._callout(icon, f"{name}: {opinion}"))
        children.append(self._divider())
        children.append(self._heading(2, "📊 핵심 시장 데이터 (Market Trends)"))
        market_table_data = report_data.get('market_table', [])
        if market_table_data:
            children.append(self._table(market_table_data))
        children.append(self._divider())
        children.append(self._callout("⚠️",
            "본 보고서는 정보 제공을 목적으로 하며, 투자 결정에 대한 최종 책임은 본인에게 있습니다.", "red_background"))

        payload = {
            "parent": {"database_id": db_id},
            "properties": {
                "Name": {"title": [{"type": "text", "text": {"content": page_title}}]},
            },
            "children": children
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Notion DB report created for {market_type}!")
                return True
            else:
                logger.error(f"Notion DB Error ({response.status_code}): {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Notion Exception: {e}")
            return False
