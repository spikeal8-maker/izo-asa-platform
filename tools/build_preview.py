"""Build the offline Windows Docker preview archive from already-built images."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BUNDLE = "IZO-ASA-Chat-Preview"
POSTGRES = "postgres:17-bookworm"
STORAGE = "chrislusf/seaweedfs:4.29"


def run(*args: str) -> None:
    subprocess.run(args, check=True, timeout=600, stdout=subprocess.DEVNULL)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compose_text(api_image: str, web_image: str, build_sha: str = "unreleased") -> str:
    text = """name: izo-chat-preview
x-api-environment: &api-environment
  IZO_ENVIRONMENT: ${IZO_ENVIRONMENT:-development}
  IZO_PG_HOST: postgres
  IZO_PG_PASSWORD: ${IZO_PG_PASSWORD:?Missing IZO_PG_PASSWORD}
  IZO_S3_ENDPOINT: http://storage:8333
  IZO_S3_ACCESS_KEY: ${IZO_S3_ACCESS_KEY:?Missing IZO_S3_ACCESS_KEY}
  IZO_S3_SECRET_KEY: ${IZO_S3_SECRET_KEY:?Missing IZO_S3_SECRET_KEY}
  IZO_BUILD_SHA: '@BUILD_SHA@'
  IZO_AUTH_RATE_SECRET: ${IZO_AUTH_RATE_SECRET:?Missing IZO_AUTH_RATE_SECRET}
  IZO_AUTH_REGISTRATION: ${IZO_AUTH_REGISTRATION:-open}
  IZO_AUTH_ORIGINS: '["http://localhost:${IZO_HTTP_PORT:-8080}","http://127.0.0.1:${IZO_HTTP_PORT:-8080}"]'
  IZO_RECOVERY_SECRET: ${IZO_RECOVERY_SECRET:-}
  IZO_RECOVERY_DELIVERY: ${IZO_RECOVERY_DELIVERY:-disabled}
  IZO_JOBS_ENABLED: 'false'
  IZO_GUEST_ENABLED: 'false'
  IZO_FAL_ENABLED: 'false'
services:
  postgres:
    image: postgres:17-bookworm
    environment:
      POSTGRES_USER: izo
      POSTGRES_DB: izo
      POSTGRES_PASSWORD: ${IZO_PG_PASSWORD:?Missing IZO_PG_PASSWORD}
    volumes: [postgres-data:/var/lib/postgresql/data]
    networks: [private]
    healthcheck:
      test: [CMD-SHELL, 'pg_isready -U izo -d izo']
      interval: 3s
      timeout: 3s
      retries: 30
  storage:
    image: chrislusf/seaweedfs:4.29
    command: [mini, '-dir=/data']
    environment:
      AWS_ACCESS_KEY_ID: ${IZO_S3_ACCESS_KEY:?Missing IZO_S3_ACCESS_KEY}
      AWS_SECRET_ACCESS_KEY: ${IZO_S3_SECRET_KEY:?Missing IZO_S3_SECRET_KEY}
      S3_BUCKET: izo-private
    volumes: [objects:/data]
    networks: [private]
  migrate:
    image: @API@
    environment: *api-environment
    command: [python, '-m', alembic, upgrade, head]
    networks: [private]
    depends_on:
      postgres: {condition: service_healthy}
  api:
    image: @API@
    environment:
      <<: *api-environment
      IZO_CHAT_ROOT_KEY: ${IZO_CHAT_ROOT_KEY:?Missing IZO_CHAT_ROOT_KEY}
      IZO_CHAT_PREVIEW_ACCOUNT_EMAILS: ${IZO_CHAT_PREVIEW_ACCOUNT_EMAILS:-preview@local.izo}
    networks: [private, chat-egress]
    read_only: true
    tmpfs: [/tmp]
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    depends_on:
      migrate: {condition: service_completed_successfully}
      storage: {condition: service_started}
    healthcheck:
      test: [CMD, python, '-c', "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=8)"]
      interval: 5s
      timeout: 10s
      retries: 30
      start_period: 15s
  web:
    image: @WEB@
    ports: ['127.0.0.1:${IZO_HTTP_PORT:-8080}:8080']
    networks: [private, edge]
    depends_on:
      api: {condition: service_healthy}
    healthcheck:
      test: [CMD, wget, '-q', '--spider', 'http://127.0.0.1:8080/']
      interval: 5s
      timeout: 3s
      retries: 20
volumes:
  postgres-data:
  objects:
networks:
  private: {internal: true}
  chat-egress: {}
  edge: {}
"""
    return text.replace("@API@", api_image).replace("@WEB@", web_image).replace("@BUILD_SHA@", build_sha)


def start_cmd() -> str:
    return r"""@echo off
setlocal
cd /d "%~dp0"
if /I "%~1"=="--check-config" goto configure
where docker >nul 2>nul || (echo Docker Desktop not found.& exit /b 1)
docker info >nul 2>nul || (echo Docker Desktop is not running.& exit /b 1)
:configure
if not exist .env (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; function New-HexSecret([int]$n){$b=New-Object byte[] $n; $r=[Security.Cryptography.RandomNumberGenerator]::Create(); $r.GetBytes($b); $r.Dispose(); ([BitConverter]::ToString($b)).Replace('-','').ToLowerInvariant()}; function New-Base64Secret([int]$n){$b=New-Object byte[] $n; $r=[Security.Cryptography.RandomNumberGenerator]::Create(); $r.GetBytes($b); $r.Dispose(); ([Convert]::ToBase64String($b)).TrimEnd('=').Replace('+','-').Replace('/','_')}; $v=@('IZO_ENVIRONMENT=development',('IZO_PG_PASSWORD='+(New-HexSecret 24)),('IZO_S3_ACCESS_KEY=izo'+(New-HexSecret 8)),('IZO_S3_SECRET_KEY='+(New-HexSecret 32)),'IZO_HTTP_PORT=8080',('IZO_AUTH_RATE_SECRET='+(New-HexSecret 32)),'IZO_AUTH_REGISTRATION=open',('IZO_RECOVERY_SECRET='+(New-HexSecret 32)),'IZO_RECOVERY_DELIVERY=disabled',('IZO_CHAT_ROOT_KEY='+(New-Base64Secret 32)),'IZO_CHAT_PREVIEW_ACCOUNT_EMAILS=preview@local.izo'); [IO.File]::WriteAllLines((Join-Path (Get-Location) '.env'),$v,[Text.Encoding]::ASCII)"
  if errorlevel 1 exit /b 1
)
if /I "%~1"=="--check-config" exit /b 0
docker load -i images.tar || exit /b 1
docker compose -p izo-chat-preview --env-file .env -f compose.yaml up -d --no-build --pull never --wait --wait-timeout 240 || (docker compose -p izo-chat-preview --env-file .env -f compose.yaml ps & exit /b 1)
echo.
echo IZO ASA preview: http://127.0.0.1:8080
echo Register with preview@local.izo, then connect your DeepSeek key in Chat.
endlocal
"""


def stop_cmd() -> str:
    return """@echo off
setlocal
cd /d "%~dp0"
if not exist .env (echo .env not found.& exit /b 1)
docker compose -p izo-chat-preview --env-file .env -f compose.yaml down
endlocal
"""


def readme(live_status: str) -> str:
    return f"""ИЗО АСА — локальный Chat preview

Требование: установлен и запущен Docker Desktop. Git, Python и Node.js не нужны.

1. Распакуйте архив целиком в отдельную папку.
2. Запустите start.cmd. Первый запуск загрузит локальные образы из images.tar и выполнит миграции.
3. Откройте http://127.0.0.1:8080
4. Создайте аккаунт с почтой preview@local.izo, именем и паролем не короче 8 символов.
5. В Chat нажмите «Подключить DeepSeek», введите свой API key и выполните проверку.
6. Выберите «Авто», DeepSeek Flash или DeepSeek V4 Pro и отправьте сообщение.
7. stop.cmd останавливает контейнеры, но сохраняет PostgreSQL/S3 volumes. Следующий start.cmd использует те же данные.

API key не находится в архиве и не отправляется в GitHub/CI. Он шифруется сервером с локальным root key из .env.
Файл .env создаётся только на вашем компьютере при первом start.cmd. Не публикуйте и не пересылайте его.
Приложение публикуется только на 127.0.0.1:8080, не в LAN/Internet.

Статус live-проверки DeepSeek при сборке: {live_status}
Это означает только статус сборочной проверки. Пользовательская проверка ключа в preview выполняет реальный запрос DeepSeek.

Проверка файлов:
  Get-FileHash .\images.tar -Algorithm SHA256
Сверьте хэши остальных файлов с checksums.sha256.
"""


def write_bundle(root: Path, *, sha: str, api_image: str, web_image: str,
                 live_status: str, source_sha: str | None = None) -> tuple[Path, dict]:
    bundle = root / BUNDLE
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)
    (bundle / "compose.yaml").write_text(
        compose_text(api_image, web_image, sha), encoding="utf-8", newline="\n")
    (bundle / "start.cmd").write_text(start_cmd(), encoding="utf-8", newline="\r\n")
    (bundle / "stop.cmd").write_text(stop_cmd(), encoding="utf-8", newline="\r\n")
    (bundle / "README-RU.txt").write_text(
        readme(live_status), encoding="utf-8", newline="\r\n")
    info = {
        "package": "CHAT-DEEPSEEK-001",
        "source_sha": source_sha or sha,
        "build_sha": sha,
        "source_base": "1120121c0fd1f6d9279aa3e95523bb48d5b906f8",
        "live_deepseek": live_status,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "images": [api_image, web_image, POSTGRES, STORAGE],
        "images_archive_compression": "gzip",
        "published_port": "127.0.0.1:8080",
    }
    (bundle / "build-info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for image in info["images"]:
        run("docker", "image", "inspect", image)
    raw_images = bundle / "images.raw.tar"
    images_archive = bundle / "images.tar"
    run("docker", "save", "-o", str(raw_images), *info["images"])
    try:
        with raw_images.open("rb") as source, images_archive.open("wb") as target:
            with gzip.GzipFile(fileobj=target, mode="wb", compresslevel=6, mtime=0) as compressed:
                shutil.copyfileobj(source, compressed, length=1024 * 1024)
    finally:
        raw_images.unlink(missing_ok=True)

    files = ["start.cmd", "stop.cmd", "compose.yaml", "images.tar",
             "build-info.json", "README-RU.txt"]
    checks = [f"{sha256(bundle / name)}  {name}" for name in files]
    (bundle / "checksums.sha256").write_text(
        "\n".join(checks) + "\n", encoding="ascii")
    return bundle, info


def archive(root: Path, bundle: Path) -> tuple[Path, int, str]:
    target = root / f"{BUNDLE}.zip"
    if target.exists():
        target.unlink()
    with zipfile.ZipFile(target, "w") as out:
        for name in ("start.cmd", "stop.cmd", "compose.yaml", "images.tar",
                     "build-info.json", "checksums.sha256", "README-RU.txt"):
            path = bundle / name
            method = zipfile.ZIP_STORED if path.name == "images.tar" else zipfile.ZIP_DEFLATED
            out.write(path, f"{BUNDLE}/{path.name}", compress_type=method)
    digest = sha256(target)
    (root / f"{BUNDLE}.zip.sha256").write_text(
        f"{digest}  {target.name}\n", encoding="ascii")
    return target, target.stat().st_size, digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--source-sha")
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--live-status", default="NOT_RUN")
    args = parser.parse_args()
    if any(len(value) != 40 or any(c not in "0123456789abcdef" for c in value)
           for value in (args.sha, args.source_sha or args.sha)):
        raise SystemExit("full lowercase SHA required")
    args.output.mkdir(parents=True, exist_ok=True)
    bundle, info = write_bundle(
        args.output, sha=args.sha, api_image=args.api_image,
        web_image=args.web_image, live_status=args.live_status, source_sha=args.source_sha)
    target, size, digest = archive(args.output, bundle)
    print(json.dumps({
        "zip": str(target), "size_bytes": size, "sha256": digest,
        "live_deepseek": info["live_deepseek"],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
