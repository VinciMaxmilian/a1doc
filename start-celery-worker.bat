@echo off
title Indoc - Celery Worker
cd /d "%~dp0backend"
echo Iniciando Celery Worker...
venv\Scripts\celery.exe -A celery_app worker --loglevel=info --pool=solo
pause
