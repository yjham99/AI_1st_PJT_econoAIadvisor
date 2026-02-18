import requests
import os

class TelegramNotifier:
    def __init__(self, token=None, chat_id=None):
        # 환경 변수 또는 직접 입력
        self.token = token or "8533023680:AAE0SnT4m2Al379nE-bF6T7_tYQewivzYeU"
        self.chat_id = chat_id or "8042300573"
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_message(self, text):
        if not self.token or self.token == "YOUR_BOT_TOKEN":
            print("[오류] Telegram Bot Token이 설정되지 않았습니다.")
            return False
            
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(self.base_url, json=payload)
            if response.json().get("ok"):
                print(f"[성공] 텔레그램 메시지 전송 완료")
                return True
            else:
                print(f"[실패] 텔레그램 전송 오류: {response.json().get('description')}")
                return False
        except Exception as e:
            print(f"[오류] 텔레그램 연동 중 문제 발생: {e}")
            return False

if __name__ == "__main__":
    # 테스트 실행
    notifier = TelegramNotifier()
    notifier.send_message("🚀 **[알파 HQ]** 시스템 연동 테스트 중입니다.")


