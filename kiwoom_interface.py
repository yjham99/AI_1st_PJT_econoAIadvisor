import json
import sys
import time
from datetime import datetime

from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QCoreApplication, QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication

from sentinel_manager import SentinelManager
from telegram_notifier import TelegramNotifier


class KiwoomInterface(QAxWidget):
    def __init__(self):
        super().__init__()
        self._load_config()
        self.manager = SentinelManager()
        self.notifier = TelegramNotifier(
            token=self.config.get("telegram", {}).get("token"),
            chat_id=self.config.get("telegram", {}).get("chat_id")
        )
        self.last_request_time = 0
        self.interval = 3  # 기본 3초 간격
        self._create_kiwoom_instance()
        self._set_signal_slots()

    def _load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"[오류] config.json 로드 실패: {e}")
            self.config = {}

    def _create_kiwoom_instance(self):
        try:
            self.setControl("KHOpenAPI.KHOpenAPICtrl.1")
        except Exception as e:
            print(f"[오류] 키움 인스턴스 생성 실패: {e}")

    def check_connection(self):
        """API 연결 상태 체크 및 자동 유지"""
        state = self.dynamicCall("GetConnectState()")
        if state == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ [경고] 연결 단절. 재접속 시도...")
            self.comm_connect()
            return False
        return True

    def _set_signal_slots(self):
        self.OnEventConnect.connect(self._event_connect)
        self.OnReceiveTrData.connect(self._receive_tr_data)
        self.OnReceiveRealData.connect(self._receive_real_data)

    def comm_connect(self):
        self.dynamicCall("CommConnect()")
        self.login_event_loop = QEventLoop()
        self.login_event_loop.exec_()

    def _event_connect(self, err_code):
        if err_code == 0:
            print("[성공] 키움 Open API 서버 접속 완료")
        else:
            print(f"[실패] 키움 Open API 서버 접속 실패 (에러코드: {err_code})")
        self.login_event_loop.exit()

    def wait_request(self):
        """트래픽 쓰로틀링 제어"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_request_time = time.time()

    def get_stock_info(self, code):
        self.wait_request()
        self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            "opt10001_req",
            "opt10001",
            0,
            "0101",
        )

    def _receive_tr_data(
        self,
        screen_no,
        rqname,
        trcode,
        recordname,
        prev_next,
        data_len,
        err_code,
        msg1,
        msg2,
    ):
        if rqname == "opt10001_req":
            name = self.dynamicCall(
                "GetCommData(QString, QString, int, QString)",
                trcode,
                recordname,
                0,
                "종목명",
            ).strip()
            price_raw = self.dynamicCall(
                "GetCommData(QString, QString, int, QString)",
                trcode,
                recordname,
                0,
                "현재가",
            ).strip()
            if not price_raw:
                return

            price = abs(int(price_raw))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{name}] 현재가: {price}원")

            # [DB 업데이트] 실시간 시세를 DB에 기록
            self.manager.update_stock_price(name, price)

            watchlist = self.manager.get_watchlist()
            for stock in watchlist:
                if stock["name"] in name:
                    # [알림 로직] 목표가 도달 체크 (목표가가 설정된 경우에만)
                    target_price = stock["target_price"]
                    current_price = price
                    stock_name = name

                    if target_price > 0:
                        # 현재가는 음수일 수 있음 (전일대비 하락 시 - 기호)
                        abs_price = abs(current_price)

                        # 근접 알림 (예: 1% 범위 내) 또는 도달 알림
                        if abs_price >= target_price:
                            msg = f"🚨 **[목표가 도달 알림]**\n종목: {stock_name}\n현재가: {abs_price:,}원\n목표가: {target_price:,}원\n\n[김대리] 사격 명령 대기 중입니다!"
                            self.notifier.send_message(msg)
                            # 중복 알림 방지를 위해 목표가 초기화 또는 로직 필요 (여기서는 일단 전송)
                            self.manager.log_alert(name, price)
                            self.manager.remove_from_watchlist(stock["name"])

    def _receive_real_data(self, code, real_type, real_data):
        if real_type == "주식체결":
            price_raw = self.dynamicCall("GetCommRealData(QString, int)", code, 10).strip()
            if not price_raw:
                return
            _price = abs(int(price_raw))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    kiwoom = KiwoomInterface()
    kiwoom.comm_connect()

    print("🛡️ [Sentinel Protocol] 키움 감시탑 가동 중...")
    while True:
        # [운영 시간 제어] 08:00 ~ 19:00 사이에만 가동
        now = datetime.now()
        start_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=19, minute=0, second=0, microsecond=0)

        if not (start_time <= now <= end_time):
            # 운영 시간 외에는 루프 속도를 늦추고 대기
            if now.second % 60 == 0: # 1분마다 로그 출력
                print(f"[{now.strftime('%H:%M:%S')}] 🌙 현재는 휴식 시간입니다. (08:00~19:00 가동)")
            time.sleep(10)
            QCoreApplication.processEvents()
            continue

        if not kiwoom.check_connection():
            time.sleep(5)
            continue

        watchlist = kiwoom.manager.get_watchlist()
        if watchlist:
            for stock in watchlist:
                ticker_map = {
                    "삼성전자": "005930",
                    "SK하이닉스": "000660",
                    "한미반도체": "042700",
                    "LG전자": "066570",
                }
                code = ticker_map.get(stock["name"], stock["name"])
                kiwoom.get_stock_info(code)

                loop = QEventLoop()
                QTimer.singleShot(1000, loop.quit)
                loop.exec_()

        QCoreApplication.processEvents()
        time.sleep(kiwoom.interval)
