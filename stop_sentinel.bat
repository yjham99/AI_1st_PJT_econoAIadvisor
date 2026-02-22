@echo off
TITLE [Alpha HQ] System Shutdown
color 0C

:: 프로젝트 경로 설정
set PROJ_DIR=c:\AI_Study_Beginer\1st_PJT_econoAIadvisor
cd /d %PROJ_DIR%

echo ======================================================
echo    [Alpha HQ] 시스템 종료 시퀀스 가동
echo ======================================================
echo.

:: 1. 특정 타이틀을 가진 창 종료 시도 (가장 안전)
echo [1/2] 가동 중인 터미널 세션 종료 중...
taskkill /FI "WINDOWTITLE eq Alpha_HQ*" /T /F >nul 2>&1

:: 2. 미처 종료되지 않은 Python 및 Kiwoom 프로세스 정리
echo [2/2] 잔류 프로세스(Python, KOAStudio) 정리 중...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM py.exe /T >nul 2>&1
taskkill /F /IM KOAStudioSA.exe /T >nul 2>&1

echo.
echo ------------------------------------------------------
echo [완료] 모든 시스템이 안전하게 종료되었습니다.
echo ------------------------------------------------------
timeout /t 3
exit
