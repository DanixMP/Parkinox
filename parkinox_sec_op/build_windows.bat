@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo ========================================
echo Parkinox Security Operator - Windows Build
echo ========================================
echo.

where flutter >nul 2>&1
if errorlevel 1 (
  echo Flutter not found on PATH. Add Flutter bin to PATH and retry.
  exit /b 1
)

echo Stopping running security app if any...
taskkill /IM parkinox_sec_op.exe /F >nul 2>&1

if not exist "build\native_assets\windows" mkdir "build\native_assets\windows"

echo.
echo Running flutter pub get...
call flutter pub get --offline
if errorlevel 1 (
  echo Offline pub get failed — retrying online...
  call flutter pub get
  if errorlevel 1 exit /b 1
)

echo.
echo Building Windows release...
call flutter build windows --release
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo   %CD%\build\windows\x64\runner\Release\parkinox_sec_op.exe
echo.
endlocal
