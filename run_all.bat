@echo off
echo ========================================
echo Starting Parkinox System
echo ========================================
echo.

echo [1/3] Starting FastAPI Server (Port 8000)...
cd /d "%~dp0Core"
start "FastAPI Server - Port 8000" cmd /k "call venv\Scripts\activate.bat && python fastapi_app.py"

echo Waiting for FastAPI to initialize...
timeout /t 3 /nobreak >nul

echo [2/3] Starting Django Backend (Port 8001)...
cd /d "%~dp0backend"
if exist env\Scripts\activate.bat (
    start "Django Backend - Port 8001" cmd /k "call env\Scripts\activate.bat && python manage.py runserver 8001"
) else if exist venv\Scripts\activate.bat (
    start "Django Backend - Port 8001" cmd /k "call venv\Scripts\activate.bat && python manage.py runserver 8001"
) else (
    start "Django Backend - Port 8001" cmd /k "python manage.py runserver 8001"
)

echo Waiting for Django to initialize...
timeout /t 3 /nobreak >nul

echo [3/3] Starting Flutter App...
cd /d "%~dp0parkinox_op"
if not exist "build\windows\x64\runner\Release\parkinox_op.exe" (
    echo Flutter executable not found. Building Windows app...
    call build_windows.bat
    if errorlevel 1 (
        echo Windows build failed. See errors above.
        pause
        exit /b 1
    )
)
start "" "build\windows\x64\runner\Release\parkinox_op.exe"

echo.
echo ========================================
echo System Started Successfully!
echo ========================================
echo FastAPI (Detection):  http://localhost:8000
echo Django (Backend):     http://localhost:8001
echo Flutter:              Running in separate window
echo.
echo Press any key to exit this window...
echo (All services will keep running)
pause >nul
