@echo off
title A1Doc - Backend (auto-reload)
cd /d "%~dp0backend"
echo Iniciando backend com auto-reload em http://localhost:8000
venv\Scripts\uvicorn.exe main:app --reload --host 0.0.0.0 --port 8000
pause
