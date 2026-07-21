@echo off
title Indoc - Backend (auto-reload)
cd /d "%~dp0backend"

echo Aplicando migrations...
venv\Scripts\alembic.exe upgrade head
if errorlevel 1 (
    echo.
    echo Falha ao aplicar as migrations. Backend nao iniciado.
    pause
    exit /b 1
)

echo Iniciando backend com auto-reload em http://localhost:8000
venv\Scripts\uvicorn.exe main:app --reload --host 0.0.0.0 --port 8000
pause
