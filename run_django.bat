@echo off
echo ========================================
echo Starting Django Backend on Port 8001
echo ========================================
echo.

cd backend

echo Activating virtual environment...
if exist env\Scripts\activate.bat (
    call env\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Warning: No virtual environment found. Using system Python.
)

echo.
echo Starting Django server on http://localhost:8001
echo Press Ctrl+C to stop
echo.

python manage.py runserver 8001

pause
