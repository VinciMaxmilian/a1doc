@echo off
title Indoc - Celery Beat
cd /d "%~dp0backend"
echo Iniciando Celery Beat (scheduler)...
venv\Scripts\celery.exe -A celery_app beat --loglevel=info
pause
