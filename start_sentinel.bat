@echo off
TITLE [Alpha HQ] Integrated Command Center
color 0A

:: 프로젝트 경로 설정
set PROJ_DIR=c:\AI_Study_Beginer\1st_PJT_econoAIadvisor
cd /d %PROJ_DIR%

echo ======================================================
echo    [Alpha HQ] 자율 기동 시스템 가동 시작
echo ======================================================
echo.

:: 1. 기존 프로세스 정리 (중복 실행 방지)
echo [1/3] 기존 세션 정리 중...
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

:: 2. 64bit 시스템 가동 (텔레그램 봇 + 데일리 스케줄러)
echo [2/3] 64bit 참모진 소집 중 (Telegram Bot, Scheduler)...
start "Alpha_HQ_Bot" cmd /k "python telegram_bot.py"
start "Alpha_HQ_Scheduler" cmd /k "python daily_scheduler.py"

:: 3. 32bit 시스템 가동 (키움 인터페이스)
echo [3/3] 32bit 감시탑 가동 중 (Kiwoom Interface)...
:: 시스템에 설치된 32bit 파이썬 경로를 명시적으로 사용하거나 py -3.10-32 활용
start "Alpha_HQ_Kiwoom" cmd /k "py -3.10-32 kiwoom_interface.py"

echo.
echo ------------------------------------------------------
echo [성공] 모든 시스템이 신규 터미널에서 가동되었습니다.
echo 본 창은 종료하셔도 백그라운드에서 요원들이 작동합니다.
echo ------------------------------------------------------
timeout /t 5
exit
