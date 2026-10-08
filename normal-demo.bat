@echo off
setlocal
cd /d "%~dp0"
title P^&ID digital twin demo: normal operation
echo.
echo  Switching the plant replay back to normal operation.
call docker compose exec -T te-sim sh -c "echo normal 0 > /tmp/te-run"
echo.
pause
