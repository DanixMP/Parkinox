@echo off
REM Run elevated once to register the durable sync task (logon + restart-on-failure).
schtasks /Delete /TN "ParkinoxSyncToCloud" /F >nul 2>&1
schtasks /Create /TN "ParkinoxSyncToCloud" /TR "F:\pilot\Parkinox-v3-M\backend\run_sync_to_cloud.bat" /SC ONLOGON /RL LIMITED /F
if errorlevel 1 (
  echo Failed to create ParkinoxSyncToCloud. Right-click this file and Run as administrator.
  pause
  exit /b 1
)
echo Task ParkinoxSyncToCloud created. Starting now...
schtasks /Run /TN "ParkinoxSyncToCloud"
schtasks /Query /TN "ParkinoxSyncToCloud" /V /FO LIST
pause
