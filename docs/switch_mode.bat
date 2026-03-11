@echo off
if "%1"=="" (
    echo Usage: switch_mode.bat day ^| night
    exit /b 1
)
if not exist "C:\CWSL_DIGI\config_%1.ini" (
    echo ERROR: config_%1.ini not found!
    exit /b 1
)
echo Stopping CWSL_DIGI...
taskkill /IM CWSL_DIGI.exe /F 2>nul
timeout /t 3 /nobreak >nul
copy /Y "C:\CWSL_DIGI\config_%1.ini" "C:\CWSL_DIGI\config.ini"
echo Switched to %1 config. Starting CWSL_DIGI...
cd /d C:\CWSL_DIGI
start "" CWSL_DIGI.exe
echo Done.
