@echo off
setlocal
cd /d "%~dp0"
if not exist .env.dev (echo .env.dev not found.& exit /b 1)
docker compose -p izo-chat-dev --env-file .env.dev -f compose.dev.yaml down --remove-orphans
endlocal
