import sys
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from datetime import datetime
import time
import json
from sentinel_manager import SentinelManager
from telegram_notifier import TelegramNotifier

class KiwoomInterface(QAxWidget):
    def __init__(self):
        super().__init__()
        self._load_config()
        self.manager = SentinelManager()
        self.notifier = TelegramNotifier()
        self.last_request_time = 0
        self.interval = 3  # 기본 3초 간격 (정차장 관리)
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
        """ [정차장] API 연결 상태 체크 및 자동 유지 """
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
        """ [정차장] 트래픽 쓰로틀링 제어 """
        elapsed = time.time() - self.last_request_time
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_request_time = time.time()

    def get_stock_info(self, code):
        self.wait_request()
        self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.dynamicCall("CommRqData(QString, QString, int, QString)", "opt10001_req", "opt10001", 0, "0101")

    def _receive_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, err_code, msg1, msg2):
        if rqname == "opt10001_req":
            name = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, recordname, 0, "종목명").strip()
            price_raw = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, recordname, 0, "현재가").strip()
            if not price_raw: return
            price = abs(int(price_raw))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{name}] 현재가: {price}원")
            
            # [Filter 1] 로컬 시세 체크 (LLM 0%)
            watchlist = self.manager.get_watchlist()
            for stock in watchlist:
                if stock["name"] in name:  # 이름 매칭
                    if stock["target_price"] > 0 and price >= stock["target_price"]:
                        msg = f"🎯 **[Sentinel Alert]** {name}가 {price}원에 도달했습니다! (목표가: {stock['target_price']}원)"
                        self.notifier.send_message(msg)
                        self.manager.log_alert(name, price)
                        self.manager.remove_from_watchlist(stock["name"])

    def _receive_real_data(self, code, real_type, real_data):
        if real_type == "주식체결":
            price_raw = self.dynamicCall("GetCommRealData(QString, int)", code, 10).strip()
            if not price_raw: return
            price = abs(int(price_raw))
            # 실시간 체결 모니터링 (필요시 추가)
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    kiwoom = KiwoomInterface()
    kiwoom.comm_connect()
    
    # [정차장] 장중 감시 시스템 가동
    print("🛡️ [Sentinel Protocol] 키움 감시탑 가동 중...")
    while True:
        if not kiwoom.check_connection():
            time.sleep(5)
            continue

        watchlist = kiwoom.manager.get_watchlist()
        if not watchlist:
            # print("감시 중인 종목이 없습니다. 대기 중...")
            pass
        else:
            for stock in watchlist:
                ticker_map = {"삼성전자": "005930", "SK하이닉스": "000660", "한미반도체": "042700"}
                code = ticker_map.get(stock["name"], stock["name"]) 
                kiwoom.get_stock_info(code)
                
                # TR 응답 대기 및 이벤트 처리
                loop = QEventLoop()
                QTimer.singleShot(1000, loop.quit)
                loop.exec_()
        
        QCoreApplication.processEvents()
        time.sleep(kiwoom.interval)








