import requests
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NotionClient:
    """
    [알파 HQ] 노션 연동 클라이언트: 시장 분석 보고서를 테이블 및 전문가 블록 형식으로 저장
    """
    def __init__(self, token, db_kr, db_us):
        self.token = token
        self.db_kr = db_kr
        self.db_us = db_us
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def _create_text_block(self, content, bold=False, italic=False, color="default"):
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": content},
                    "annotations": {"bold": bold, "italic": italic, "color": color}
                }]
            }
        }

    def _create_heading(self, level, text):
        return {
            "object": "block",
            "type": f"heading_{level}",
            [f"heading_{level}"]: {"rich_text": [{"type": "text", "text": {"content": text}}]}
        }

    def _create_callout(self, icon, text, color="default"):
        return {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "icon": {"emoji": icon},
                "color": color
            }
        }

    def _create_table(self, rows_data):
        """
        rows_data: List of lists, where the first list is the header.
        """
        table_rows = []
        for row in rows_data:
            cells = []
            for cell in row:
                cells.append([{"type": "text", "text": {"content": str(cell)}}])
            table_rows.append({
                "object": "block",
                "type": "table_row",
                "table_row": {"cells": cells}
            })

        return {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": len(rows_data[0]),
                "has_column_header": True,
                "has_row_header": False,
                "children": table_rows
            }
        }

    def send_report(self, market_type, report_data):
        """
        market_type: 'KR' or 'US'
        report_data: dict containing title, experts, trends, links, etc.
        """
        db_id = self.db_kr if market_type == 'KR' else self.db_us
        if not db_id or "ENTER_" in db_id:
            logger.warning(f"Notion Database ID for {market_type} is missing or not set.")
            return False

        url = "https://api.notion.com/v1/pages"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        page_title = f"🛡️ [{market_type}] {report_data.get('title', '시장 통합 보고서')} ({current_time})"

        children = []
        
        # 1. 전문가 의견 (Callouts)
        children.append(self._create_heading(2, "🎙️ 참모진 통합 의견 (Expert Sync)"))
        experts = report_data.get('experts', {})
        for name, opinion in experts.items():
            # 이름에 '캐빈', '총장', 'Cabin'이 포함되면 고래 아이콘 사용
            icon = "🐋" if any(x in name.upper() for x in ["CABIN", "캐빈", "총장"]) else "📈"
            children.append(self._create_callout(icon, f"{name}: {opinion}"))

        children.append({"object": "block", "type": "divider", "divider": {}})

        # 2. 시장 데이터 (Table)
        children.append(self._create_heading(2, "📊 핵심 시장 데이터 (Market Trends)"))
        market_table_data = report_data.get('market_table', [])
        if market_table_data:
            children.append(self._create_table(market_table_data))
        else:
            children.append(self._create_text_block("수집된 데이터가 없습니다.", italic=True, color="gray"))

        children.append({"object": "block", "type": "divider", "divider": {}})

        # 3. 참고 자료 및 링크
        children.append(self._create_heading(2, "🔗 참고 자료 및 인텔리전스"))
        links = report_data.get('links', [])
        for link in links:
            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"{link['name']}: "}},
                        {"type": "text", "text": {"content": link['url'], "link": {"url": link['url']}}}
                    ]
                }
            })

        # 4. 리스크 고지
        children.append({"object": "block", "type": "divider", "divider": {}})
        children.append(self._create_callout("⚠️", "본 보고서는 정보 제공을 목적으로 하며, 투자 결정에 대한 최종 책임은 본인에게 있습니다.", "red_background"))

        payload = {
            "parent": {"database_id": db_id},
            "properties": {
                "Name": {"title": [{"type": "text", "text": {"content": page_title}}]},
                "Market": {"select": {"name": market_type}},
                "Date": {"date": {"start": datetime.now().isoformat()}}
            },
            "children": children
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Notion report created successfully for {market_type}!")
                return True
            else:
                logger.error(f"Notion Error ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"Notion Exception: {e}")
            return False
