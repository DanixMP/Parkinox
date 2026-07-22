@echo off
cd /d F:\pilot\Parkinox-v3-M\backend
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set DJANGO_SETTINGS_MODULE=config.settings.development

if not exist "logs" mkdir logs

:loop
echo [%date% %time%] starting sync_to_cloud >> "logs\sync_to_cloud.log"
"E:\app\anaconda\python.exe" manage.py sync_to_cloud --sleep 5 >> "logs\sync_to_cloud.log" 2>&1
echo [%date% %time%] sync_to_cloud exited with %ERRORLEVEL% — restarting in 10s >> "logs\sync_to_cloud.log"
timeout /t 10 /nobreak >nul
goto loop
