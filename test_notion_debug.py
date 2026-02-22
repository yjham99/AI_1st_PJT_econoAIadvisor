"""Summary 페이지 전체 보고서 디버깅 - 블록 하나씩 전송하여 문제 위치 확인"""
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

url = f"https://api.notion.com/v1/blocks/{page_id}/children"

# macro_data_text 시뮬레이션
macro_text = "- Nasdaq: 16,320.50 (0.12%)\n- S&P 500: 6,800.00 (-0.05%)\n- USD/KRW: 1,352.40 (-0.21%)\n- US 10Y Yield: 4.52 (0.03%)"

# 테스트할 블록 그룹들
test_groups = {
    "1. 헤딩+디바이더": [
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "2026-02-18 12:15 DEBUG TEST"}}]}},
        {"object": "block", "type": "divider", "divider": {}},
    ],
    "2. 캐빈 Callout": [
        {"object": "block", "type": "callout", "callout": {"rich_text": [{"type": "text", "text": {"content": "캐빈: 리스크 테스트"}}], "icon": {"emoji": "🐋"}, "color": "default"}},
    ],
    "3. 키워드 H3+텍스트": [
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": "핵심 키워드"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "금리, AI, 지정학"}, "annotations": {"bold": True, "italic": False, "color": "default"}}]}},
    ],
    "4. 매크로 지표 (bullet)": [
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": "매크로 지표 현황"}}]}},
    ] + [
        {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line.strip().lstrip("- ")}}]}}
        for line in macro_text.strip().split("\n") if line.strip()
    ],
    "5. 모델 정보": [
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Intelligence Efficiency"}}]}},
        {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "Active Models: gemini-3-flash, claude-4.5-sonnet"}}]}},
    ],
    "6. 리스크 고지": [
        {"object": "block", "type": "callout", "callout": {"rich_text": [{"type": "text", "text": {"content": "투자 결정에 대한 최종 책임은 본인에게 있습니다."}}], "icon": {"emoji": "⚠️"}, "color": "red_background"}},
    ],
}

print("=" * 50)
for name, blocks in test_groups.items():
    r = requests.patch(url, headers=headers, json={"children": blocks}, timeout=30)
    status = "✅" if r.status_code == 200 else f"❌ ({r.status_code})"
    print(f"{name}: {status}")
    if r.status_code != 200:
        print(f"  Error: {r.text[:300]}")
print("=" * 50)
print("디버깅 완료!")
