"""Notion KR 페이지 테이블 내용 세부 확인"""
import requests
import json

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

token = config["notion"]["token"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

pid = config["notion"]["page_kr"]

all_results = []
has_more = True
next_cursor = None

while has_more:
    url = f"https://api.notion.com/v1/blocks/{pid}/children"
    if next_cursor: url += f"?start_cursor={next_cursor}"
    r = requests.get(url, headers=headers, timeout=10)
    data = r.json()
    all_results.extend(data.get("results", []))
    has_more = data.get("has_more", False)
    next_cursor = data.get("next_cursor")

print(f"KR 총 블록: {len(all_results)}")

# 마지막 테이블 블록 찾기
tables = [b for b in all_results if b.get("type") == "table"]
if tables:
    last_table = tables[-1]
    tid = last_table["id"]
    # 테이블 행 가져오기
    r = requests.get(f"https://api.notion.com/v1/blocks/{tid}/children", headers=headers)
    rows = r.json().get("results", [])
    print("\n--- [최신 테이블 행 내용] ---")
    for row in rows:
        cells = row.get("table_row", {}).get("cells", [])
        row_text = []
        for cell in cells:
            row_text.append(cell[0].get("plain_text", "") if cell else "")
        print(" | ".join(row_text))
else:
    print("테이블을 찾지 못했습니다.")
