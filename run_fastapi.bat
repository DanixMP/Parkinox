@echo off
echo Starting FastAPI Server...
cd /d "%~dp0Core"
call venv\Scripts\activate.bat
python fastapi_app.py
pause
