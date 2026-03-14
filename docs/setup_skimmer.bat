@echo off
REM ============================================================================
REM  Skimmer Setup Script - CW Skimmer Server + CWSL_Tee + CWSL_DIGI
REM  For Red Pitaya STEMlab 125-14 (rp-f09804, 192.168.1.54)
REM  Run as Administrator!
REM ============================================================================

setlocal

REM --- Configuration ---
set SHARE=\\192.168.1.101\motorola
set SKIMSRV_DIR=C:\Program Files (x86)\Afreet\SkimSrv
set CWSL_DIGI_DIR=C:\CWSL_DIGI
set WSJTX_BIN=C:\WSJT\wsjtx\bin
set AGGREGATOR_DIR=C:\RBNAggregator
set CALLSIGN=WF8Z
set GRID=EM79sm
set PITAYA_IP=192.168.1.54
set HERMESINTF_DLL=HermesIntf

REM --- Check for admin ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo ============================================================================
echo  Skimmer Setup Script
echo  Callsign: %CALLSIGN%  Grid: %GRID%
echo  Pitaya: %PITAYA_IP%
echo ============================================================================
echo.

REM --- Step 1: Install IPP70 (Intel Primitives) ---
echo [1/8] Installing Intel IPP70 libraries to SysWOW64...
if not exist "%SHARE%\cwsl_tee\CWSL-master\bin\IPP70\" (
    echo ERROR: IPP70 folder not found on share!
    pause
    exit /b 1
)
xcopy "%SHARE%\cwsl_tee\CWSL-master\bin\IPP70\*" "C:\Windows\SysWOW64\" /D /Y >nul 2>&1
echo   Done.
echo.

REM --- Step 2: Install VC++ Redistributable (x86) ---
echo [2/8] Installing VC++ 2010 Redistributable (x86)...
if exist "%SHARE%\cwsl_tee\CWSL-master\bin\vcredist_x86.exe" (
    "%SHARE%\cwsl_tee\CWSL-master\bin\vcredist_x86.exe" /q /norestart
    echo   Done.
) else (
    echo   WARNING: vcredist_x86.exe not found, skipping.
)
echo.

REM --- Step 2b: Install VC++ 2022 Redistributable (x64) ---
echo [2b/8] Installing VC++ 2022 Redistributable (x64)...
if exist "%SHARE%\cwsl_digi\vc_redist.x64.exe" (
    "%SHARE%\cwsl_digi\vc_redist.x64.exe" /quiet /norestart
    echo   Done.
) else (
    echo   WARNING: vc_redist.x64.exe not found, skipping.
)
echo.

REM --- Step 3: Install CWSL_Tee into SkimSrv ---
echo [3/8] Installing CWSL_Tee into SkimSrv...
if not exist "%SKIMSRV_DIR%" (
    echo   WARNING: SkimSrv directory not found at %SKIMSRV_DIR%
    echo   Install CW Skimmer Server first, then re-run this script.
    pause
    exit /b 1
)
REM CRITICAL: Must use 2017 CWSL_Tee.dll (18,432 bytes) from CWSL.zip
REM The 2014 GoodOldStable version (17,408 bytes) does NOT create shared memory!
copy "%SHARE%\cwsl_tee\CWSL_Tee.dll" "%SKIMSRV_DIR%\" /Y >nul
echo   Copied CWSL_Tee.dll (2017 version from CWSL.zip)

REM --- Write CWSL_Tee.cfg pointing to HermesIntf ---
echo HermesIntf> "%SKIMSRV_DIR%\CWSL_Tee.cfg"
echo 8>> "%SKIMSRV_DIR%\CWSL_Tee.cfg"
echo   Wrote CWSL_Tee.cfg (HermesIntf, buffer depth 8)
echo.

REM --- Step 4: Verify HermesIntf DLL exists ---
echo [4/8] Checking for HermesIntf DLL...
if exist "%SKIMSRV_DIR%\%HERMESINTF_DLL%.dll" (
    echo   Found: %HERMESINTF_DLL%.dll
) else (
    echo   WARNING: %HERMESINTF_DLL%.dll not found in %SKIMSRV_DIR%
    echo   Download latest from: https://github.com/k3it/HermesIntf/releases
    echo   Rename to %HERMESINTF_DLL%.dll and place in %SKIMSRV_DIR%
)
echo.

REM --- Step 5: Install CWSL_DIGI ---
echo [5/8] Installing CWSL_DIGI...
if not exist "%CWSL_DIGI_DIR%" mkdir "%CWSL_DIGI_DIR%"
if not exist "%CWSL_DIGI_DIR%\wave" mkdir "%CWSL_DIGI_DIR%\wave"

copy "%SHARE%\cwsl_digi\CWSL_DIGI-main\CWSL_DIGI.exe" "%CWSL_DIGI_DIR%\" /Y >nul
copy "%SHARE%\cwsl_digi\CWSL_DIGI-main\Qt5Core.dll" "%CWSL_DIGI_DIR%\" /Y >nul
echo   Copied CWSL_DIGI.exe and Qt5Core.dll
echo   Created wave temp directory
echo.

REM --- Step 6: Write CWSL_DIGI config files (all modes) ---
echo [6/8] Installing CWSL_DIGI config files and scripts...

REM Copy mode configs from share
copy "%SHARE%\config_night.ini" "%CWSL_DIGI_DIR%\" /Y >nul
copy "%SHARE%\config_day.ini" "%CWSL_DIGI_DIR%\" /Y >nul
copy "%SHARE%\config_night_rare.ini" "%CWSL_DIGI_DIR%\" /Y >nul
copy "%SHARE%\config_day_rare.ini" "%CWSL_DIGI_DIR%\" /Y >nul
echo   Copied mode configs (day, night, day_rare, night_rare)

REM Copy switch_mode.bat
copy "%SHARE%\switch_mode.bat" "%CWSL_DIGI_DIR%\" /Y >nul
echo   Copied switch_mode.bat

REM Copy watch_call.ps1 (call monitor with TCP server)
copy "%SHARE%\watch_call.ps1" "%CWSL_DIGI_DIR%\" /Y >nul
echo   Copied watch_call.ps1 (call monitor, port 7777)

REM Set default config to night
copy "%CWSL_DIGI_DIR%\config_night.ini" "%CWSL_DIGI_DIR%\config.ini" /Y >nul
echo   Default config: night (80/40/20m FT8)
echo.

REM --- Step 7: Install RBN Aggregator ---
echo [7/8] Installing RBN Aggregator...
if not exist "%AGGREGATOR_DIR%" mkdir "%AGGREGATOR_DIR%"
if exist "%SHARE%\RBNAggregator\*" (
    xcopy "%SHARE%\RBNAggregator\*" "%AGGREGATOR_DIR%\" /D /Y >nul 2>&1
    echo   Copied RBN Aggregator to %AGGREGATOR_DIR%
) else (
    echo   WARNING: RBN Aggregator not found on share.
    echo   Download v6.7 and place in %SHARE%\RBNAggregator\
)
echo.

REM --- Step 8: Disable sleep/hibernate ---
echo [8/8] Disabling sleep, hibernate, and monitor timeout...
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 0
echo   Done.
echo.

REM --- Summary ---
echo ============================================================================
echo  Setup Complete!
echo ============================================================================
echo.
echo  INSTALLED:
echo   - CWSL_Tee.dll (2017, 18432 bytes) in SkimSrv dir
echo   - CWSL_Tee.cfg (HermesIntf, buffer depth 8)
echo   - CWSL_DIGI with mode configs (day/night/day_rare/night_rare)
echo   - switch_mode.bat (mode switching)
echo   - watch_call.ps1 (call monitor on TCP port 7777)
echo   - RBN Aggregator
echo   - Sleep/hibernate disabled
echo.
echo  MANUAL STEPS:
echo   1. Ensure HermesIntf.dll (v24.1.13+) is in:
echo      %SKIMSRV_DIR%
echo      Download: https://github.com/k3it/HermesIntf/releases
echo.
echo   2. Install Intel Fortran redistributable (for CWSL_DIGI/jt9.exe):
echo      https://drive.google.com/drive/folders/1pk99ruANXTd_87oLce2L32H2V-P6dAFn
echo.
echo   3. Install WSJT-X to %WSJTX_BIN%
echo      (only jt9.exe and wsprd.exe are needed)
echo.
echo   4. Start Red Pitaya (ssh root@%PITAYA_IP%):
echo      cd /root ^&^& ./start.sh
echo.
echo   5. Start SkimSrv, select "CWSL_Tee on RP-F09804" as receiver
echo      Configure: 8 bands (80/40/30/20/17/15/12/10m), 192kHz, ThreadCount 3
echo.
echo   6. Start RBN Aggregator:
echo      - Set callsign to %CALLSIGN%-2
echo      - Enable input port 2215 (CWSL_DIGI feed)
echo      - Set output telnet port to 7550
echo      - Connect to RBN
echo.
echo   7. Start CWSL_DIGI (pick one):
echo      a. Simple:    %CWSL_DIGI_DIR%\switch_mode.bat night
echo      b. Monitored: powershell -ExecutionPolicy Bypass -File %CWSL_DIGI_DIR%\watch_call.ps1 -Mode night
echo         Then connect: telnet [this-pc-ip] 7777
echo.
echo   8. Verify shared memory (all 8 segments):
echo      handle64.exe -p SkimSrv.exe ^| findstr CWSL
echo      Should show CWSL0Band through CWSL7Band
echo.
echo   9. Set BIOS "After Power Loss" to "Power On" (needs physical access)
echo.
echo  MODE SWITCHING:
echo   switch_mode.bat day          - Normal FT8 (20/17/15/12/10m)
echo   switch_mode.bat night        - Normal FT8 (80/40/20m)
echo   switch_mode.bat day_rare     - DXpedition (20/17/15/12/10m F/H freqs)
echo   switch_mode.bat night_rare   - DXpedition (80/40/30/20m F/H freqs)
echo.
echo ============================================================================
pause
