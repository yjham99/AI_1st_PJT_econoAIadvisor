import os
import json
import requests
from notion_client import NotionClient
from datetime import datetime

def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def send_slack(token, channel, text):
    print(f"Sending to Slack channel {channel}...")
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json={"channel": channel, "text": text}, timeout=10)
        res_data = response.json()
        if res_data.get("ok"):
            print(f"[Success] Slack message sent.")
        else:
            print(f"[Failed] Slack error: {res_data.get('error')}")
    except Exception as e:
        print(f"[Error] Slack connection failed: {e}")

def markdown_to_notion_blocks(md_text, client):
    blocks = []
    lines = md_text.split('\n')
    
    # Add title block
    blocks.append(client._heading(1, f"Investment Report ({datetime.now().strftime('%Y-%m-%d')})"))
    blocks.append(client._divider())

    for line in lines:
        line = line.strip()
        if not line: continue
        
        if line.startswith('# '):
            blocks.append(client._heading(1, line[2:]))
        elif line.startswith('## '):
            blocks.append(client._heading(2, line[3:]))
        elif line.startswith('### '):
            blocks.append(client._heading(3, line[4:]))
        elif line.startswith('- '):
            blocks.append(client._bullet(line[2:]))
        elif line.startswith('> '):
            blocks.append(client._callout("💡", line[2:]))
        elif line.startswith('|'):
            # Table handling is complex in simple parser, treat as code block or text
            # For simplicity, just text for now, or code block
            blocks.append(client._text_block(line, color="gray"))
        else:
            blocks.append(client._text_block(line))
            
    return blocks

def main():
    config = load_config()
    
    # Read Report
    if not os.path.exists('investment_report.md'):
        print("Report file not found!")
        return
        
    with open('investment_report.md', 'r', encoding='utf-8') as f:
        report_text = f.read()

    # 1. Slack
    slack_cfg = config.get('slack', {})
    if slack_cfg.get('token') and slack_cfg.get('channel_daily'):
        send_slack(slack_cfg['token'], slack_cfg['channel_daily'], report_text)
    else:
        print("Slack config missing.")

    # 2. Notion
    notion_cfg = config.get('notion', {})
    if notion_cfg.get('token') and notion_cfg.get('page_summary'):
        print("Sending to Notion...")
        try:
            client = NotionClient(
                token=notion_cfg['token'],
                page_summary=notion_cfg['page_summary']
            )
            
            blocks = markdown_to_notion_blocks(report_text, client)
            success = client._append_blocks(client.page_summary, blocks)
            if success:
                print("[Success] Notion report appended.")
            else:
                print("[Failed] Notion append failed.")
        except Exception as e:
            print(f"[Error] Notion processing failed: {e}")
    else:
        print("Notion config missing.")

if __name__ == "__main__":
    main()
