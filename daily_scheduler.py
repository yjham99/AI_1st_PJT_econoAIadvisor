import schedule
import time
import subprocess
import sys
from datetime import datetime

def run_analysis(mode="daily"):
    print(f"[{datetime.now()}] Triggering {mode} analysis...")
    try:
        # Use sys.executable to ensure we use the same environment
        subprocess.run([sys.executable, "market_scanner.py", mode], check=True)
    except Exception as e:
        print(f"Error during {mode} run: {e}")

# --- 스케줄링 설정 ---

# 1. 월요일 ~ 금요일: 08:30, 12:00, 16:00
for t in ["08:30", "12:00", "16:00"]:
    schedule.every().monday.at(t).do(run_analysis, mode="daily")
    schedule.every().tuesday.at(t).do(run_analysis, mode="daily")
    schedule.every().wednesday.at(t).do(run_analysis, mode="daily")
    schedule.every().thursday.at(t).do(run_analysis, mode="daily")
    schedule.every().friday.at(t).do(run_analysis, mode="daily")

# 2. 토요일: 12:00 (일일 보고 1회)
schedule.every().saturday.at("12:00").do(run_analysis, mode="daily")

# 3. 일요일: 12:00 (주간 요약 보고)
schedule.every().sunday.at("12:00").do(run_analysis, mode="weekly")

print(f"[{datetime.now()}] AI Automation Lab Advanced Scheduler started.")
print("- Mon-Fri: 08:30, 12:00, 16:00")
print("- Sat: 12:00")
print("- Sun: 12:00 (Weekly Summary)")

if __name__ == "__main__":
    last_heartbeat = 0
    while True:
        schedule.run_pending()
        
        # 1시간마다 생존 신고 (로그 용)
        current_time = time.time()
        if current_time - last_heartbeat > 3600:
            print(f"[{datetime.now()}] Scheduler is alive and watching...")
            last_heartbeat = current_time
            
        time.sleep(30)
