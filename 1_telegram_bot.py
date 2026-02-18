import requests
import time
import json
from sentinel_manager import SentinelManager
from telegram_notifier import TelegramNotifier

class SentinelBot:
    def __init__(self):
        self._load_config()
        self.manager = SentinelManager()
        self.notifier = TelegramNotifier()
        self.token = self.notifier.token
        self.offset = 0
        self.set_commands() # 시작 시 메뉴 설정
        
        # [NEW] 유동적 참모진 설정
        self.staff = self.config.get("staff", {})

    def _load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"[오류] config.json 로드 실패: {e}")
            self.config = {}

    def _get_staff_name(self, role_or_id, default="시스템"):
        """역할(role) 또는 ID를 기반으로 참모 이름을 반환"""
        if role_or_id in self.staff:
            return self.staff[role_or_id].get("name", default)
        for s in self.staff.values():
            if s.get("role") == role_or_id:
                return s.get("name", default)
        return default

    def set_commands(self):
        """ 텔레그램 '메뉴' 버튼에 명령어 등록 """
        if not self.token: return
        url = f"https://api.telegram.org/bot{self.token}/setMyCommands"
        commands = [
            {"command": "add", "description": "감시 종목 추가 (예: /add 삼성전자 80000)"},
            {"command": "del", "description": "감시 종목 삭제 (예: /del 삼성전자)"},
            {"command": "list", "description": "현재 감시 리스트 확인"},
            {"command": "help", "description": "전체 명령어 도움말"}
        ]
        try:
            requests.post(url, json={"commands": commands})
            print("[성공] 텔레그램 메뉴 명령어 설정 완료")
        except Exception as e:
            print(f"[오류] 메뉴 설정 실패: {e}")

    def get_updates(self):
        if not self.token: return []
        url = f"https://api.telegram.org/bot{self.token}/getUpdates?offset={self.offset}"
        try:
            res = requests.get(url).json()
            return res.get("result", [])
        except:
            return []

    def handle_command(self, chat_id, text, sender_name="Unknown"):
        # 입력 전처리
        text = text.replace('"', '').replace("'", "").strip()
        parts = text.split()
        if not parts: return

        cmd = parts[0].lower()

        # 2. 자연어 처리/종목 추가
        if not text.startswith("/"):
            stock_input = text.strip()
            if len(parts) <= 2:
                res = self.manager.add_to_watchlist(stock_input, 0)
                current_price_str = self._get_current_price_str(stock_input)
                # [NEW] 동적 참모 이름 적용
                echo_name = self._get_staff_name("Echo", "정차장")
                self.notifier.send_message(f"✅ {res}{current_price_str}\n\n[{echo_name}] 실시간 감시를 시작합니다.")
            else:
                source = "세사모" if "세사모" in sender_name else sender_name
                self.manager.log_intel(source, text)
            return

        # 3. 명령어 처리
        if cmd == "/add":
            if len(parts) >= 2:
                name = parts[1]
                price = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
                res = self.manager.add_to_watchlist(name, price)
                current_price_str = self._get_current_price_str(name)
                self.notifier.send_message(f"{res}{current_price_str}")
            else:
                self.notifier.send_message("❌ 사용법: /add [종목명] [목표가(선택)]")
        
        elif cmd == "/del" and len(parts) >= 2:
            name = parts[1]
            res = self.manager.remove_from_watchlist(name)
            self.notifier.send_message(res)

        elif cmd == "/list":
            watchlist = self.manager.get_watchlist()
            if not watchlist:
                self.notifier.send_message("🛡️ 현재 감시 중인 종목이 없습니다.")
            else:
                msg_lines = ["🛡️ **[현재 감시 리스트]**"]
                for i in watchlist:
                    name = i['name']
                    target = i['target_price']
                    price_info = self._get_current_price_str(name)
                    if target == 0:
                         msg_lines.append(f"- {name}: 목표가 미설정{price_info}")
                    else:
                         msg_lines.append(f"- {name}: 목표가 {target:,}원{price_info}")
                self.notifier.send_message("\n".join(msg_lines))
        
        elif cmd == "/help":
            msg = "🤖 **센티널 프로토콜 명령 체계**\n\n1. **종목 바로 추가**: 그냥 '삼성전자' 입력\n2. **/add [종목] [가격]**: 목표가와 함께 추가\n3. **/del [종목]**: 감시 삭제\n4. **/list**: 현재 리스트 확인"
            self.notifier.send_message(msg)

    def _get_current_price_str(self, stock_name):
        import yfinance as yf
        ticker = self.manager.find_ticker(stock_name)
        if not ticker: return ""
        try:
            stock = yf.Ticker(ticker)
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            return f" (현재가: {int(current_price):,}원)"
        except: return ""

    def run(self):
        print("Sentinel Bot (Legacy/Lite) 가동 중...")
        while True:
            updates = self.get_updates()
            for update in updates:
                msg = update.get("message")
                if msg and "text" in msg:
                    sender = msg.get("from", {}).get("first_name", "Unknown")
                    chat_title = msg.get("chat", {}).get("title", sender)
                    self.handle_command(msg["chat"]["id"], msg["text"], chat_title)
                self.offset = update["update_id"] + 1
            time.sleep(2)

if __name__ == "__main__":
    bot = SentinelBot()
    bot.run()
