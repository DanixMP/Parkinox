@echo off

setlocal EnableDelayedExpansion

echo ========================================

echo Starting Parkinox System

echo ========================================

echo.



REM --- Find Python with FastAPI (Core) ---

set "FASTAPI_PY="

for /f "delims=" %%P in ('where python 2^>nul') do call :TryFastApiPython "%%P"

if not defined FASTAPI_PY (

  py -3 -c "import fastapi" >nul 2>&1

  if not errorlevel 1 (

    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)"') do set "FASTAPI_PY=%%P"

  )

)

if not defined FASTAPI_PY (

  echo [ERROR] No Python with FastAPI found.

  echo Install: cd Core ^&^& py -3 -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt

  pause

  exit /b 1

)

echo FastAPI Python: !FASTAPI_PY!



echo [1/3] Starting FastAPI Server (Port 8002)...

cd /d "%~dp0Core"

start "FastAPI Server - Port 8002" cmd /k ""!FASTAPI_PY!" fastapi_app.py"



echo Waiting for FastAPI to initialize...

timeout /t 3 /nobreak >nul



REM --- Find Python with Django (backend) ---

set "DJANGO_PY="

for /f "delims=" %%P in ('where python 2^>nul') do call :TryDjangoPython "%%P"

if not defined DJANGO_PY (

  py -3 -c "import django" >nul 2>&1

  if not errorlevel 1 (

    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)"') do set "DJANGO_PY=%%P"

  )

)

if not defined DJANGO_PY (

  echo [ERROR] No Python with Django found.

  echo The backend\env venv may be broken ^(copied from another PC^).

  echo Recreate: cd backend ^&^& py -3 -m venv env ^&^& env\Scripts\pip install -r requirements.txt

  pause

  exit /b 1

)

echo Django Python: !DJANGO_PY!



echo [2/3] Starting Django Backend (Port 8001, ASGI/Daphne)...

cd /d "%~dp0backend"

start "Django Backend - Port 8001" cmd /k "cd /d %~dp0backend && "!DJANGO_PY!" -m daphne -b 127.0.0.1 -p 8001 config.asgi:application"



echo Waiting for Django to initialize...

timeout /t 5 /nobreak >nul



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

echo FastAPI (Detection):  http://localhost:8002

echo Django (Backend):     http://localhost:8001

echo Flutter:              Running in separate window

echo.

echo Press any key to exit this window...

echo (All services will keep running)

pause >nul

goto :eof



:TryDjangoPython

if defined DJANGO_PY goto :eof

"%~1" -c "import django" >nul 2>&1

if errorlevel 1 goto :eof

set "DJANGO_PY=%~1"

goto :eof



:TryFastApiPython

if defined FASTAPI_PY goto :eof

"%~1" -c "import fastapi" >nul 2>&1

if errorlevel 1 goto :eof

set "FASTAPI_PY=%~1"

goto :eof

