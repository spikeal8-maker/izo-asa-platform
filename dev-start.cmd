@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>nul || (echo Docker Desktop not found.& exit /b 1)
docker info >nul 2>nul || (echo Docker Desktop is not running.& exit /b 1)

if not exist .env.dev (
  docker volume inspect izo-chat-dev_postgres-data >nul 2>nul
  if not errorlevel 1 (
    echo Existing izo-chat-dev database found but .env.dev is missing.
    echo Restore the original .env.dev with its IZO_CHAT_ROOT_KEY.
    echo No replacement root key was generated.
    exit /b 2
  )
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; function Hex([int]$n){$b=New-Object byte[] $n;$r=[Security.Cryptography.RandomNumberGenerator]::Create();$r.GetBytes($b);$r.Dispose();([BitConverter]::ToString($b)).Replace('-','').ToLowerInvariant()}; function B64([int]$n){$b=New-Object byte[] $n;$r=[Security.Cryptography.RandomNumberGenerator]::Create();$r.GetBytes($b);$r.Dispose();([Convert]::ToBase64String($b)).TrimEnd('=').Replace('+','-').Replace('/','_')}; $v=@('IZO_ENVIRONMENT=development','IZO_DEV_PORT=5190',('IZO_PG_PASSWORD='+(Hex 24)),('IZO_S3_ACCESS_KEY=izo'+(Hex 8)),('IZO_S3_SECRET_KEY='+(Hex 32)),('IZO_AUTH_RATE_SECRET='+(Hex 32)),('IZO_RECOVERY_SECRET='+(Hex 32)),('IZO_CHAT_ROOT_KEY='+(B64 32)),'IZO_CHAT_LOCAL_PREVIEW_ENABLED=true'); [IO.File]::WriteAllLines((Join-Path (Get-Location) '.env.dev'),$v,[Text.Encoding]::ASCII)"
  if errorlevel 1 exit /b 1
)
findstr /R /B /C:"IZO_CHAT_ROOT_KEY=." .env.dev >nul || (
  echo Existing .env.dev has no usable IZO_CHAT_ROOT_KEY.
  echo Refusing to generate a replacement over persistent dev data.
  exit /b 2
)
findstr /X /C:"IZO_ENVIRONMENT=development" .env.dev >nul || (
  echo .env.dev must use IZO_ENVIRONMENT=development.
  exit /b 2
)
findstr /B /C:"IZO_CHAT_LOCAL_PREVIEW_ENABLED=" .env.dev >nul
if errorlevel 1 (
  >>.env.dev echo IZO_CHAT_LOCAL_PREVIEW_ENABLED=true
) else (
  findstr /X /C:"IZO_CHAT_LOCAL_PREVIEW_ENABLED=true" .env.dev >nul || (
    echo .env.dev must enable IZO_CHAT_LOCAL_PREVIEW_ENABLED=true.
    exit /b 2
  )
)
findstr /B /C:"IZO_DEV_PORT=" .env.dev >nul || >>.env.dev echo IZO_DEV_PORT=5190

set "NEED_BUILD=0"
docker image inspect izo-chat-dev-api:local >nul 2>nul || set "NEED_BUILD=1"
docker image inspect izo-chat-dev-web:local >nul 2>nul || set "NEED_BUILD=1"
if "%NEED_BUILD%"=="1" (
  docker compose -p izo-chat-dev --env-file .env.dev -f compose.dev.yaml build api web || exit /b 1
)
docker compose -p izo-chat-dev --env-file .env.dev -f compose.dev.yaml up -d postgres storage || exit /b 1
docker compose -p izo-chat-dev --env-file .env.dev -f compose.dev.yaml run --rm migrate || exit /b 1
docker compose -p izo-chat-dev --env-file .env.dev -f compose.dev.yaml up -d api web --wait --wait-timeout 240 || (
  docker compose -p izo-chat-dev --env-file .env.dev -f compose.dev.yaml ps
  exit /b 1
)

set "DEV_PORT=5190"
for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"IZO_DEV_PORT=" .env.dev') do set "DEV_PORT=%%B"
echo.
echo IZO ASA Docker dev: http://127.0.0.1:%DEV_PORT%
echo Source edits under apps/web/src use Vite HMR.
echo Source edits under apps/api/izo use Uvicorn reload.
endlocal
