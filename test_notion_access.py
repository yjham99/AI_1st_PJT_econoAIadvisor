"""Notion 페이지 접근 테스트"""
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

pages = {
    "Summary (통합요약)": "30b4cfa8d8c780dcb512ef1debaa0574",
    "Korea Market": "30b4cfa8d8c7808298a5e6b010d56ad2",
    "America Market": "30b4cfa8d8c78051bb06ded65f553489"
}

print("=" * 50)
print("Notion 페이지 접근 테스트")
print("=" * 50)

all_ok = True
for name, pid in pages.items():
    r = requests.get(f"https://api.notion.com/v1/pages/{pid}", headers=headers, timeout=10)
    status = "✅ 접근 가능" if r.status_code == 200 else f"❌ 접근 불가 ({r.status_code})"
    print(f"[{name}] {status}")
    if r.status_code != 200:
        all_ok = False
        data = r.json()
        print(f"  → 오류: {data.get('message', 'Unknown')}")

print()
if all_ok:
    print("🎉 모든 페이지 접근 가능! 보고서 전송 준비 완료.")
else:
    print("⚠️ 일부 페이지에 접근할 수 없습니다.")
    print("   → Notion에서 해당 페이지의 '연결(Connections)'에 'AI Studio'를 추가해주세요.")
