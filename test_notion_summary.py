"""Summary 페이지 테스트 & 디버깅"""
import requests
import json

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

token = config["notion"]["token"]
page_id = config["notion"]["page_summary"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 간단한 블록으로 테스트
blocks = [
    {
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "2026-02-18 12:10 통합 시장 브리핑 (테스트)"}}]}
    },
    {
        "object": "block", "type": "divider", "divider": {}
    },
    {
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": "캐빈: 리스크 관리를 위해 현금 10% 비중 유지는 필수입니다."}}],
            "icon": {"emoji": "🐋"}, "color": "default"
        }
    },
    {
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": "최부장: 글로벌 매크로 키워드: 금리 인하 신중, AI 가속기 독점, 지정학적 리스크 완화"}}],
            "icon": {"emoji": "📈"}, "color": "default"
        }
    },
    {
        "object": "block", "type": "heading_3",
        "heading_3": {"rich_text": [{"type": "text", "text": {"content": "핵심 키워드"}}]}
    },
    {
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": [{
            "type": "text", "text": {"content": "금리 인하 신중, AI 가속기 독점, 지정학적 리스크 완화"},
            "annotations": {"bold": True, "italic": False, "color": "default"}
        }]}
    }
]

url = f"https://api.notion.com/v1/blocks/{page_id}/children"
response = requests.patch(url, headers=headers, json={"children": blocks}, timeout=30)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("✅ Summary 페이지에 블록 추가 성공!")
else:
    print(f"❌ 오류: {response.text[:500]}")
