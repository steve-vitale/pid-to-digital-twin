@echo off
setlocal
cd /d "%~dp0"
title P&ID digital twin demo: stopping
echo.
echo  Stopping the demo. Nothing is deleted: start-demo.bat brings it back.
echo  (Stopping and starting also restarts Ignition's 2-hour trial timer.)
echo.
docker compose stop
echo.
echo  Stopped. To remove the demo completely (frees about 2 GB): run  docker compose down -v
echo.
pause
