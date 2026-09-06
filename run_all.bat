echo off
title 당직 알림 시스템 전체 실행
echo ========================================================
echo 터미널 1 :대시보드(streamlit)
echo 터미널 2 :알림 로봇(worker)
echo ========================================================
echo.

start "Dashboard" cmd  /k "streamlit run app.py"
timeout /t 3 /nobreak >nul
start "Worker" cmd /k "python worker.py"

echo 두창이 떳습니다. 이창은 닫으셔도 됩니다.
pause