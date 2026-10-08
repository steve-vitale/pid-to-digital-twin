@echo off
setlocal
cd /d "%~dp0"
title P&ID digital twin demo: fault 6
echo.
echo  Switching the plant replay to fault 6 (loss of A feed).
echo  Watch the reactor pressure (PI-107) on the plant screen: it turns red in about 30 seconds.
echo.
set TE_RUN=fault6
set TE_START=236
docker compose up -d te-sim
echo.
echo  To go back to normal operation: double-click normal-demo.bat
echo.
pause
