@echo off
setlocal
cd /d "%~dp0"
title P^&ID digital twin demo
echo.
echo  P^&ID digital twin demo: starting
echo  ---------------------------------
echo.

call docker info >nul 2>&1
if errorlevel 1 (
  echo  Docker Desktop is not running.
  echo  Open Docker Desktop from the Start menu, wait until it says "Engine running",
  echo  then double-click this file again.
  echo.
  pause
  exit /b 1
)

echo  Starting Ignition and the two data servers.
echo  The first time takes several minutes: it downloads Ignition (about 1 GB).
echo.
call docker compose up -d --build
if errorlevel 1 (
  echo.
  echo  Something went wrong starting the demo. The messages above say what.
  echo  Common fix: make sure nothing else on this computer is using port 8088.
  pause
  exit /b 1
)

echo.
echo  Waiting for Ignition to finish starting...
powershell -NoProfile -Command "$t=Get-Date; while (((Get-Date)-$t).TotalMinutes -lt 15) { try { if ((Invoke-WebRequest -UseBasicParsing http://localhost:8088/StatusPing -TimeoutSec 3).Content -match '\"RUNNING\"}') { exit 0 } } catch {}; Start-Sleep 3 }; exit 1"
if errorlevel 1 (
  echo  Ignition did not finish starting within 15 minutes.
  echo  Try again with stop-demo.bat, then start-demo.bat.
  pause
  exit /b 1
)
rem The screens subscribe to live data a few seconds after the gateway reports it is running.
powershell -NoProfile -Command "Start-Sleep 10"

echo.
echo  Ready. Opening the plant screen in your browser:
echo    http://localhost:8088/data/perspective/client/PIDTwin
echo  The extracted drawings are at .../PIDTwin/open100/0 through /open100/11
echo.
echo  To see the alarm: double-click fault-demo.bat (reactor pressure turns red in about 30 seconds).
echo  To stop: double-click stop-demo.bat.
echo  Ignition runs as a 2-hour trial. To get 2 more hours: open http://localhost:8088,
echo  click "Log In to Reset", and sign in as admin / ChangeMe-TwinDemo1 (see docker\README.md).
start "" "http://localhost:8088/data/perspective/client/PIDTwin"
echo.
pause
