#!/usr/bin/env bash
set -euo pipefail
api_tag="izo-asa-chat-api:${GITHUB_SHA::12}"
web_tag="izo-asa-chat-web:${GITHUB_SHA::12}"
docker tag "$(docker compose images -q api | head -n1)" "$api_tag"
docker tag "$(docker compose images -q web | head -n1)" "$web_tag"
rm -rf "$RUNNER_TEMP/izo-preview" "$RUNNER_TEMP/izo-preview-clean"
mkdir -p "$RUNNER_TEMP/izo-preview"
.venv/bin/python tools/build_preview.py \
  --output "$RUNNER_TEMP/izo-preview" --sha "$GITHUB_SHA" --source-sha "$IZO_SOURCE_SHA" \
  --api-image "$api_tag" --web-image "$web_tag" \
  --live-status "NOT_RUN/BLOCKED" > "$RUNNER_TEMP/izo-preview/result.json"
unzip -q "$RUNNER_TEMP/izo-preview/IZO-ASA-Chat-Preview.zip" \
  -d "$RUNNER_TEMP/izo-preview-clean"
bundle="$RUNNER_TEMP/izo-preview-clean/IZO-ASA-Chat-Preview"
test -f "$bundle/start.cmd" -a -f "$bundle/stop.cmd" -a -f "$bundle/compose.yaml"
test -f "$bundle/images.tar" -a -f "$bundle/build-info.json"
test -f "$bundle/checksums.sha256" -a -f "$bundle/README-RU.txt"
if grep -q 'build:' "$bundle/compose.yaml"; then echo "Preview must not build"; exit 1; fi
(cd "$bundle" && sha256sum -c checksums.sha256)
docker image rm "$api_tag" "$web_tag"
docker load -i "$bundle/images.tar" >/dev/null
docker image inspect "$api_tag" "$web_tag" >/dev/null
chat_root="$(.venv/bin/python -c "import base64; print(base64.urlsafe_b64encode(b'x'*32).decode().rstrip('='))")"
cat > "$bundle/.env" <<EOF
IZO_ENVIRONMENT=test
IZO_PG_PASSWORD=ci-preview-pg-password-2026
IZO_S3_ACCESS_KEY=izopreviewaccess
IZO_S3_SECRET_KEY=ci-preview-storage-secret-2026-0000
IZO_HTTP_PORT=18080
IZO_AUTH_RATE_SECRET=rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr
IZO_AUTH_REGISTRATION=open
IZO_RECOVERY_SECRET=ssssssssssssssssssssssssssssssssssssssssssssssss
IZO_RECOVERY_DELIVERY=test
IZO_CHAT_ROOT_KEY=$chat_root
IZO_CHAT_PREVIEW_ACCOUNT_EMAILS=preview@local.izo,search@local.izo
EOF
preview="docker compose -f $bundle/compose.yaml -p izo-chat-preview-clean --env-file $bundle/.env"
$preview up -d --wait --wait-timeout 240
test "$(docker network inspect izo-chat-preview-clean_private --format '{{.Internal}}')" = true
test "$(docker network inspect izo-chat-preview-clean_chat-egress --format '{{.Internal}}')" = false
for service in postgres storage; do
  container="$($preview ps -q "$service")"
  test "$(docker inspect "$container" --format '{{len .NetworkSettings.Networks}}')" = 1
  test "$(docker inspect "$container" --format '{{len .HostConfig.PortBindings}}')" = 0
done
echo PREVIEW_NETWORK_POLICY_OK
.venv/bin/python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:18080/api/health/ready',timeout=10).status==200"
IZO_CHAT_ACCEPTANCE=isolated IZO_CHAT_ORIGIN=http://127.0.0.1:18080 \
  node apps/web/acceptance/chat-live.mjs "$RUNNER_TEMP/izo-preview-chat.json" before
$preview down
$preview up -d --wait --wait-timeout 180
.venv/bin/python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:18080/api/health/ready',timeout=10).status==200"
IZO_CHAT_ACCEPTANCE=isolated IZO_CHAT_ORIGIN=http://127.0.0.1:18080 \
  node apps/web/acceptance/chat-live.mjs "$RUNNER_TEMP/izo-preview-chat.json" after
$preview down -v --remove-orphans
rm -f "$RUNNER_TEMP/izo-preview-chat.json"
