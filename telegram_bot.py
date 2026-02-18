import time
from datetime import datetime
import json
import requests

from sentinel_manager import SentinelManager
from telegram_notifier import TelegramNotifier


class SentinelBot:
    def __init__(self):
        self._load_config()
        self.manager = SentinelManager()
        self.notifier = TelegramNotifier(
            token=self.config.get("telegram", {}).get("token"),
            chat_id=self.config.get("telegram", {}).get("chat_id")
        )
        self.token = self.notifier.token
        self.offset = 0
        self.set_commands()  # 시작 시 메뉴 설정
        
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
        """역할(role) 또는 ID를 기반으로 참모 이름을 반환 (config.json 기준)"""
        # 1. ID로 검색 (CABIN, JUNG 등)
        if role_or_id in self.staff:
            return self.staff[role_or_id].get("name", default)
        
        # 2. 역할(role)로 검색 (Echo, Tech, Biz, Cabin)
        for s in self.staff.values():
            if s.get("role") == role_or_id:
                return s.get("name", default)
        
        return default

    def set_commands(self):
        """텔레그램 '메뉴' 버튼에 명령어 등록"""
        if not self.token:
            print("[경고] Telegram token 미설정으로 메뉴 명령어 등록을 건너뜜")
            return

        url = f"https://api.telegram.org/bot{self.token}/setMyCommands"
        commands = [
            {"command": "add", "description": "감시 추가 (예: 삼성전자 80000)"},
            {"command": "del", "description": "감시 삭제 (예: /del 삼성전자)"},
            {"command": "list", "description": "현재 감시 리스트 확인"},
            {"command": "clear", "description": "모든 감시 종목 초기화"},
            {"command": "help", "description": "사용 방법 안내"},
        ]
        try:
            requests.post(url, json={"commands": commands}, timeout=10)
            print("[성공] 텔레그램 메뉴 명령어 설정 완료")
        except Exception as e:
            print(f"[오류] 메뉴 설정 실패: {e}")

    def get_updates(self):
        if not self.token:
            return []
        url = f"https://api.telegram.org/bot{self.token}/getUpdates?offset={self.offset}"
        try:
            res = requests.get(url, timeout=20).json()
            return res.get("result", [])
        except Exception:
            return []

    def handle_command(self, chat_id, text, sender_name="Unknown"):
        # 1. 입력 전처리
        text = text.replace('"', '').replace("'", "").strip()
        parts = text.split()
        if not parts: return

        cmd = parts[0].lower()

        # 2. 자연어 처리 (슬래시 명령어가 아닐 때)
        if not text.startswith("/"):
            # 정밀 분석 키워드
            is_clear = ("전부" in text or "모두" in text or "다 " in text) and ("지워" in text or "삭제" in text or "초기화" in text)
            is_delete = any(word in text for word in ["지워", "삭제", "빼줘", "제거"])
            is_price = "가격" in text or text.endswith("?")

            # (1) 전체 삭제
            if is_clear:
                res = self.manager.clear_watchlist()
                self.notifier.send_message(f"🧹 {res}")
                return

            # (2) 자연어 삭제
            if is_delete:
                target_name = text
                for word in ["지워줘", "지워", "삭제해줘", "삭제해", "삭제", "빼줘", "빼", "제거해줘", "제거", " "]:
                    target_name = target_name.replace(word, "")
                target_name = target_name.strip()
                
                if not target_name:
                    self.notifier.send_message("❌ 삭제할 **종목명을 알려주세요**. (예: 삼성전자 지워줘)")
                else:
                    res = self.manager.remove_from_watchlist(target_name)
                    self.notifier.send_message(f"🗑️ {res}")
                return

            # (3) 자연어 가격 문의
            if is_price:
                target_name = text
                for word in ["가격", "알려줘", "알려", "뭐야", "?", " "]:
                    target_name = target_name.replace(word, "")
                target_name = target_name.strip()
                
                if not target_name:
                    self.notifier.send_message("❌ 조회할 **종목명을 알려주세요**. (예: 삼성전자 가격 알려줘)")
                else:
                    price, source = self._get_current_price(target_name)
                    if price:
                        watchlist = self.manager.get_watchlist()
                        target_price = 0
                        for item in watchlist:
                            if item["name"].lower() == target_name.lower():
                                target_price = item.get("target_price", 0)
                                break
                        target_info = f" (목표가: {target_price:,}원)" if target_price > 0 else " (목표가 미설정)"
                        
                        msg = (
                            f"📊 **[{target_name}]** 정보 보고\n"
                            f"- 현재가: **{price:,}원**\n"
                            f"- 정보출처: {source}\n"
                            f"{target_info}\n\n"
                            "⚠️ **[투자 리스크]** 본 데이터는 참고용이며, 실제 매매 결과는 투자자 본인에게 귀속됩니다."
                        )
                        self.notifier.send_message(msg)
                    else:
                        self.notifier.send_message(f"❓ **[{target_name}]** 시세 조회가 불가능합니다.")
                return

            # (4) 쉼표 구분 대량 추가
            stock_inputs = [s.strip() for s in text.split(",") if s.strip()]
            if len(stock_inputs) > 0:
                valid_stocks = [s for s in stock_inputs if len(s) >= 2]
                if not valid_stocks:
                    self.notifier.send_message("❌ 추가할 **종목명을 2글자 이상** 알려주세요.")
                    return
                
                success_list = []
                for s_input in valid_stocks:
                    self.manager.add_to_watchlist(s_input, 0)
                    price, source = self._get_current_price(s_input)
                    price_str = f"({price:,}원)" if price else ""
                    success_list.append(f"{s_input}{price_str}")
                
                # [NEW] 동적 참모 이름 적용
                echo_name = self._get_staff_name("Echo", "정차장")
                self.notifier.send_message(f"✅ **[대량 추가 완료]**\n{', '.join(success_list)}\n\n[{echo_name}] 레이더 가동을 시작합니다.")
            return

        # 3. 슬래시 명령어 처리
        if cmd == "/add":
            if len(parts) >= 2:
                raw_names = " ".join(parts[1:])
                if "," in raw_names:
                    names = [n.strip() for n in raw_names.split(",") if n.strip()]
                    for n in names: self.manager.add_to_watchlist(n, 0)
                    self.notifier.send_message(f"✅ {len(names)}개 종목 추가 완료 (목표가 미설정)")
                else:
                    name = parts[1]
                    price = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
                    self.manager.add_to_watchlist(name, price)
                    current_price, source = self._get_current_price(name)
                    price_info = f" (현재가: {current_price:,}원)" if current_price else " (현재가 조회 실패)"
                    msg = f"✅ **[{name}]** 추가 완료!\n{price_info}" + (f" / 목표가: {price:,}원)" if price > 0 else ")")
                    self.notifier.send_message(msg)
            else:
                self.notifier.send_message("❌ 사용법: `/add 삼성전자 80000` 또는 `삼성전자, 현대차`와 같이 나열")

        elif cmd == "/del":
            if len(parts) >= 2:
                raw_input = " ".join(parts[1:])
                names = [n.strip() for n in raw_input.split(",") if n.strip()]
                results = [self.manager.remove_from_watchlist(n) for n in names]
                self.notifier.send_message("\n".join(results))
            else:
                self.notifier.send_message("❌ 삭제할 종목명을 입력해주세요. (예: /del 삼성전자)")

        elif cmd == "/clear":
            res = self.manager.clear_watchlist()
            self.notifier.send_message(f"🧹 {res}")

        elif cmd == "/list":
            watchlist = self.manager.get_watchlist()
            if not watchlist:
                self.notifier.send_message("🛡️ 현재 감시 중인 종목이 없습니다.")
            else:
                now = datetime.now()
                is_market = 8 <= now.hour < 19
                time_info = "실시간 라이브" if is_market else "장 종료 후 (DB 저장 데이터)"
                
                msg_lines = [f"🛡️ **[현재 감시 리스트]** ({time_info})"]
                for i in watchlist:
                    name = i["name"]
                    target = i["target_price"]
                    price = i.get("current_price", 0)
                    
                    if price == 0: # DB에 없으면 실시간 조회 시도
                        price, _ = self._get_current_price(name)
                    
                    if not price: continue
                    msg_lines.append(f"- {name}: {price:,}원" + (f" (목표: {target:,}원)" if target > 0 else ""))

                msg_lines.append("\n⚠️ **[공지]** 비영업 시간에는 마지막 수집 가격이 보존됩니다.")
                
                if len(msg_lines) <= 2:
                    self.notifier.send_message("🛡️ 유효한 시세 데이터가 없습니다.")
                else:
                    self.notifier.send_message("\n".join(msg_lines))

        elif cmd == "/help":
            msg = (
                "🤖 **센티널 프로토콜 명령 가이드**\n\n"
                "1. **종목 추가 (자연어)**\n"
                "   - 그냥 `삼성전자` 입력 (0원 감시)\n"
                "   - `삼성전자, 현대차, SK하이닉스` (대량 추가)\n"
                "2. **종목 추가 (명령어)**\n"
                "   - `/add 삼성전자 80000` (목표가 설정)\n"
                "3. **시세 확인**\n"
                "   - `삼성전자 가격 알려줘` 또는 `현대차 가격?`\n"
                "4. **종목 삭제**\n"
                "   - `삼성전자 지워줘` 또는 `/del 삼성전자`\n"
                "   - `/clear` (전체 삭제)\n"
                "5. **리스트 도표**\n"
                "   - `/list` 입력"
            )
            self.notifier.send_message(msg)

    def _get_current_price(self, stock_name):
        """ 시간대별 지능형 시세 조회 (운영 시간: 실시간, 외: DB) """
        now = datetime.now()
        is_market_time = 8 <= now.hour < 19
        
        # 1. 운영 시간 외에는 DB 데이터 우선 조회 시도
        if not is_market_time:
            watchlist = self.manager.get_watchlist()
            for item in watchlist:
                if item["name"].lower() == stock_name.lower():
                    price = item.get("current_price", 0)
                    if price > 0:
                        return price, "DB (장 종료 후 마지막 현재가)"

        # 2. 운영 시간 중이거나 DB에 데이터가 없는 경우 실시간 조회
        import yfinance as yf
        ticker = self.manager.find_ticker(stock_name)
        if not ticker:
            clean_name = stock_name.strip()
            if clean_name.isdigit() and len(clean_name) == 6:
                ticker = f"{clean_name}.KS"
            elif clean_name.isalpha():
                ticker = clean_name
            else:
                temp_map = {"삼성전자": "005930.KS", "sk하이닉스": "000660.KS", "한미반도체": "042700.KS", "lg전자": "066570.KS"}
                for k, v in temp_map.items():
                    if k in stock_name.lower() or stock_name.lower() in k:
                        ticker = v
                        break
        
        if not ticker: return 0, "조회 불가"

        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period="1d")
            if data.empty and ".KS" in ticker:
                alt_ticker = ticker.replace(".KS", ".KQ")
                stock = yf.Ticker(alt_ticker)
                data = stock.history(period="1d")
            if not data.empty:
                return int(data["Close"].iloc[-1]), "실시간 (yfinance)"
            return 0, "조회 실패"
        except Exception:
            return 0, "오류 발생"

    def run(self):
        print("Sentinel Bot 가동 중...")
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
