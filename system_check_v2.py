
import json
import requests
import psycopg2
import os

def check_db(url):
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        ver = cur.fetchone()
        cur.close()
        conn.close()
        return True, f"PostgreSQL Version: {ver[0]}"
    except Exception as e:
        return False, str(e)

def check_slack(token):
    url = "https://slack.com/api/auth.test"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.post(url, headers=headers, timeout=5)
        data = r.json()
        if data.get("ok"):
            return True, f"Slack OK: User={data.get('user')}, Team={data.get('team')}"
        else:
            return False, f"Slack Error: {data.get('error')}"
    except Exception as e:
        return False, str(e)

def check_telegram(token):
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get("ok"):
            res = data.get("result")
            return True, f"Telegram OK: Bot={res.get('username')}"
        else:
            return False, f"Telegram Error: {data.get('description')}"
    except Exception as e:
        return False, str(e)

def check_notion(token):
    url = "https://api.notion.com/v1/users/me"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28"
    }
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        if r.status_code == 200:
            return True, f"Notion OK: Name={data.get('name')}"
        else:
            return False, f"Notion Error ({r.status_code}): {data.get('message')}"
    except Exception as e:
        return False, str(e)

def main():
    if not os.path.exists("config.json"):
        print("❌ config.json not found!")
        return

    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    results = []
    
    # DB
    db_url = config.get("db", {}).get("url")
    if db_url:
        ok, msg = check_db(db_url)
        results.append(("DB", ok, msg))
    else:
        results.append(("DB", False, "Missing URL"))

    # Slack
    slack_token = config.get("slack", {}).get("token")
    if slack_token:
        ok, msg = check_slack(slack_token)
        results.append(("Slack", ok, msg))
    else:
        results.append(("Slack", False, "Missing Token"))

    # Telegram
    tg_token = config.get("telegram", {}).get("token")
    if tg_token:
        ok, msg = check_telegram(tg_token)
        results.append(("Telegram", ok, msg))
    else:
        results.append(("Telegram", False, "Missing Token"))

    # Notion
    notion_token = config.get("notion", {}).get("token")
    if notion_token:
        ok, msg = check_notion(notion_token)
        results.append(("Notion", ok, msg))
    else:
        results.append(("Notion", False, "Missing Token"))

    print("\n=== Alpha HQ System Connectivity Check ===")
    for service, ok, msg in results:
        status = "✅" if ok else "❌"
        print(f"{status} {service:8}: {msg}")
    print("==========================================")

if __name__ == "__main__":
    main()
