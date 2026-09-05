@echo off
title Subtitle AI ASR Backend Server
echo ========================================================
echo   Subtitle AI - Real-Time Streaming ASR Backend
echo ========================================================
echo.

cd /d "%~dp0\backend"
echo [1/2] Checking Python dependencies...
pip install -r requirements.txt

echo.
echo [2/2] Starting FastAPI Uvicorn Server at http://127.0.0.1:8000 ...
python main.py

pause
