"""Bounded Docker development-loop regression checks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dev_compose_is_loopback_isolated_and_live_mounted():
    compose = read("compose.dev.yaml")
    assert "name: izo-chat-dev" in compose
    assert "'127.0.0.1:${IZO_DEV_PORT:-5190}:5173'" in compose
    assert compose.count("ports:") == 1
    assert "./apps/web/src:/app/apps/web/src" in compose
    assert "./apps/api:/app/apps/api:ro" in compose
    assert "--reload-dir" in compose and "/app/apps/api" in compose
    assert "IZO_CHAT_LOCAL_PREVIEW_ENABLED: 'true'" in compose
    assert "private: {internal: true}" in compose
    assert "networks: [private, chat-egress]" in compose
    assert "networks: [private, edge]" in compose


def test_dev_vite_has_docker_hmr_and_same_origin_proxy():
    vite = read("apps/web/vite.config.ts")
    assert "IZO_VITE_API_TARGET" in vite
    assert "IZO_VITE_HMR_CLIENT_PORT" in vite
    assert "usePolling: true" in vite
    assert "proxy: { '/api':" in vite
    assert "http://127.0.0.1:8000" in vite

def test_dev_scripts_preserve_volumes_and_root_key():
    start = read("dev-start.cmd")
    stop = read("dev-stop.cmd")
    rebuild = read("dev-rebuild.cmd")
    joined = start + stop + rebuild
    assert "izo-chat-dev_postgres-data" in start
    assert "No replacement root key was generated" in start
    assert 'IZO_CHAT_ROOT_KEY=.' in start
    assert "docker compose -p izo-chat-dev" in start
    assert "run --rm migrate" in start
    assert "IZO_DEV_PORT=5190" in start
    assert " down --remove-orphans" in stop
    assert " build api web" in rebuild
    assert "down -v" not in joined
    assert "prune" not in joined


def test_stable_preview_builder_is_not_dev_wired():
    stable = read("tools/build_preview.py")
    assert "compose.dev.yaml" not in stable
    assert "IZO_DEV_PORT" not in stable
    assert "izo-chat-dev" not in stable
