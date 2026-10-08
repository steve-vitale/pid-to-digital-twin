@echo off
setlocal
cd /d "%~dp0"
title P^&ID digital twin demo: normal operation
echo.
echo  Switching the plant replay back to normal operation.
set TE_RUN=normal
set TE_START=0
call docker compose up -d te-sim
echo.
pause
