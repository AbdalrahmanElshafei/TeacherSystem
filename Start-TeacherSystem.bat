@echo off
chcp 65001 > nul
title TeacherSystem — نظام إدارة المعلم

echo ========================================================
echo   TeacherSystem — تشغيل نظام إدارة المعلم
echo ========================================================
echo.
echo [1/2] جارٍ فتح المتصفح على واجهة النظام...
start "" http://127.0.0.1:8000
echo [2/2] جارٍ تشغيل خادم FastAPI المحلي...
cd /d "%~dp0"

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
