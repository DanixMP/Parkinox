@echo off
echo Starting Flutter App...
cd /d "%~dp0parkinox_op"
start "" "build\windows\x64\runner\Release\parkinox_op.exe"
echo Flutter app started!
pause
