@echo off
setlocal
cd /d "%~dp0"
title P^&ID digital twin demo: fault 6
echo.
echo  Switching the plant replay to fault 6 (loss of A feed).
echo  Watch the reactor pressure (PI-107) on the plant screen: it turns red in about 30 seconds.
echo.
call docker compose exec -T te-sim sh -c "echo fault6 236 > /tmp/te-run"
echo.
echo  To go back to normal operation: double-click normal-demo.bat
echo.
pause
