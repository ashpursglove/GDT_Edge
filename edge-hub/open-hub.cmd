@echo off
REM From edge-hub folder: bring up Docker (Windows compose file) and open the UI in your default browser.
REM Requires Docker Desktop running.

setlocal
cd /d "%~dp0"

if exist "docker-compose.windows.yml" (
  docker compose -f docker-compose.windows.yml up -d
) else (
  docker compose -f docker-compose.dist.yml up -d
)

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8756"
