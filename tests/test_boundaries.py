"""Small executable architecture checks, not a new governance framework."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_contracts_are_independent():
    source = ast.parse((ROOT / "apps/api/izo/contracts.py").read_text())
    for node in ast.walk(source):
        if isinstance(node, ast.Import):
            assert all(a.name.split(".")[0] in {"enum", "typing", "uuid", "pydantic"} for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module.split(".")[0] in {"enum", "typing", "uuid", "pydantic"}


def test_generation_has_no_infrastructure_dependencies():
    source = ast.parse((ROOT / "apps/api/izo/generation.py").read_text())
    for node in ast.walk(source):
        if isinstance(node, ast.ImportFrom):
            assert node.module in {"collections.abc", "contracts"}
        assert not isinstance(node, ast.Import)


def test_no_giant_handwritten_source_files():
    for root in [ROOT / "apps/api/izo", ROOT / "apps/web/src"]:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".css"} and ".generated." not in path.name:
                text = path.read_text()
                assert len(text.splitlines()) <= 400, path
                assert len(text.encode()) <= 20000, path


def test_frontend_http_is_centralized():
    for path in (ROOT / "apps/web/src").rglob("*.tsx"):
        assert not re.search(r"\bfetch\s*\(", path.read_text()), path


def test_only_web_port_is_published_and_network_is_private():
    compose = (ROOT / "compose.yaml").read_text()
    assert compose.count("ports:") == 1
    assert "127.0.0.1:${IZO_HTTP_PORT:-8080}:8080" in compose
    assert "internal: true" in compose
    assert "condition: service_completed_successfully" in compose
    assert "condition: service_healthy" in compose


def test_no_production_deploy_or_self_hosted_ci():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "pull_request_target" not in ci
    assert "self-hosted" not in ci
    assert "contents: read" in ci
    assert "secrets." not in ci


def test_dependency_lock_matches_web_manifest():
    import json
    manifest = json.loads((ROOT / "apps/web/package.json").read_text())
    lock = json.loads((ROOT / "apps/web/package-lock.json").read_text())
    assert lock["lockfileVersion"] == 3
    for group in ("dependencies", "devDependencies"):
        assert lock["packages"][""][group] == manifest[group]
        for name, version in manifest[group].items():
            assert lock["packages"]["node_modules/" + name]["version"] == version


def test_dependency_lock_is_required_not_bootstrapped_in_ci():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    dockerfile = (ROOT / "infra/web.Dockerfile").read_text()
    assert "npm install" not in ci
    assert "npm install" not in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "-r requirements-dev.txt" in ci
    assert "-r requirements.lock" in (ROOT / "infra/api.Dockerfile").read_text()


def test_provider_secret_is_worker_only_and_live_provider_is_opt_in():
    compose = (ROOT / "compose.yaml").read_text()
    shared, services = compose.split("services:", 1)
    assert "IZO_OPENROUTER_API_KEY" not in shared
    assert "IZO_OPENROUTER_MODEL" in shared and "IZO_OPENROUTER_PRICE_CREDITS" in shared
    assert "IZO_OPENROUTER_RESOLUTIONS" in shared and "IZO_OPENROUTER_ENABLED" in shared
    worker = services.split("  openrouter-worker:", 1)[1].split("  web:", 1)[0]
    assert "IZO_OPENROUTER_API_KEY" in worker
    assert "<<: *api-environment" in worker
    assert "${IZO_OPENROUTER_ENABLED:-false}" in shared
    assert "networks: [private, edge]" in worker
    api = services.split("  api:", 1)[1].split("  job-worker:", 1)[0]
    assert "OPENROUTER_API_KEY" not in api
