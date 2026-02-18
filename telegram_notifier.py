import os

import requests


class TelegramNotifier:
    def __init__(self, token=None, chat_id=None):
        # Prefer explicit parameters, then environment variables.
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_message(self, text):
        if not self.token:
            print("[오류] Telegram Bot Token이 설정되지 않았습니다.")
            return False
        if not self.chat_id:
            print("[오류] Telegram Chat ID가 설정되지 않았습니다.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            response = requests.post(self.base_url, json=payload, timeout=10)
            data = response.json()
            if data.get("ok"):
                print("[성공] 텔레그램 메시지 전송 완료")
                return True

            print(f"[실패] 텔레그램 전송 오류: {data.get('description')}")
            return False
        except Exception as e:
            print(f"[오류] 텔레그램 연동 중 문제 발생: {e}")
            return False


if __name__ == "__main__":
    notifier = TelegramNotifier()
    notifier.send_message("🚀 **[알파 HQ]** 시스템 연동 테스트 중입니다.")
