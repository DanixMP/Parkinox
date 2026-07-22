@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo ========================================
echo Parkinox Operator - Windows Build
echo ========================================
echo.

where flutter >nul 2>&1
if errorlevel 1 (
  echo Flutter not found on PATH. Add Flutter bin to PATH and retry.
  exit /b 1
)

for /f "delims=" %%i in ('where flutter') do set "FLUTTER_BAT=%%i"
for %%i in ("%FLUTTER_BAT%") do set "FLUTTER_ROOT=%%~dpi.."
set "VS_DART=%FLUTTER_ROOT%\packages\flutter_tools\lib\src\windows\visual_studio.dart"

if exist "%VS_DART%" (
  findstr /C:"18 => 'Visual Studio 18 2026'" "%VS_DART%" >nul
  if errorlevel 1 (
    echo Applying Visual Studio 2026 patch to Flutter SDK...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$path = '%VS_DART%';" ^
      "$text = Get-Content -Raw $path;" ^
      "if ($text -notmatch \"18 => 'Visual Studio 18 2026'\") {" ^
      "  $text = $text -replace \"return switch \\(_majorVersion\\) \\{\\r?\\n      17 => 'Visual Studio 17 2022',\", \"return switch (_majorVersion) {`r`n      18 => 'Visual Studio 18 2026',`r`n      17 => 'Visual Studio 17 2022',\";" ^
      "  Set-Content -Path $path -Value $text -NoNewline;" ^
      "  Write-Host 'Patch applied.';" ^
      "} else { Write-Host 'Patch already present.' }"
    if errorlevel 1 (
      echo Failed to patch Flutter SDK for Visual Studio 2026.
      exit /b 1
    )
    echo Refreshing Flutter tool cache...
    del /f /q "%FLUTTER_ROOT%\bin\cache\flutter_tools.snapshot" >nul 2>&1
    del /f /q "%FLUTTER_ROOT%\bin\cache\flutter_tools.stamp" >nul 2>&1
  ) else (
    echo Visual Studio 2026 Flutter patch already applied.
  )
)

echo Stopping running operator app if any...
taskkill /IM parkinox_op.exe /F >nul 2>&1

echo Removing stale Windows build cache...
if exist "build\windows" rmdir /s /q "build\windows"

if not exist "build\native_assets\windows" mkdir "build\native_assets\windows"

echo.
echo Running flutter pub get...
call flutter pub get
if errorlevel 1 exit /b 1

echo.
echo Building Windows release...
call flutter build windows --release
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo   %CD%\build\windows\x64\runner\Release\parkinox_op.exe
echo.
endlocal
