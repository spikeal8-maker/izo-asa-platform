@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>nul || (echo Docker Desktop not found.& exit /b 1)
docker info >nul 2>nul || (echo Docker Desktop is not running.& exit /b 1)
if not exist .env.dev (echo Run dev-start.cmd once to create .env.dev.& exit /b 1)
docker compose -p izo-chat-dev --env-file .env.dev -f compose.dev.yaml build api web
endlocal
