"""Small executable architecture checks, not a new governance framework."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_contracts_are_independent():
    source = ast.parse((ROOT / "apps/api/izo/contracts.py").read_text(encoding="utf-8"))
    for node in ast.walk(source):
        if isinstance(node, ast.Import):
            assert all(a.name.split(".")[0] in {"enum", "typing", "uuid", "pydantic"} for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module.split(".")[0] in {"enum", "typing", "uuid", "pydantic"}


def test_generation_has_no_infrastructure_dependencies():
    source = ast.parse((ROOT / "apps/api/izo/generation.py").read_text(encoding="utf-8"))
    for node in ast.walk(source):
        if isinstance(node, ast.ImportFrom):
            assert node.module in {"collections.abc", "contracts"}
        assert not isinstance(node, ast.Import)


def _check_file_budget(root: Path, suffixes: set[str], *, max_lines: int, max_bytes: int):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes or ".generated." in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= max_lines, path
        assert len(text.encode("utf-8")) <= max_bytes, path


def test_handwritten_files_stay_modular():
    # Product code must stay especially small because coding agents read it frequently.
    _check_file_budget(ROOT / "apps/api/izo", {".py"}, max_lines=300, max_bytes=12_000)
    _check_file_budget(ROOT / "apps/web/src", {".ts", ".tsx", ".css"}, max_lines=300, max_bytes=12_000)
    # Tests/tools may carry fixtures, but they still must not become hidden monoliths.
    _check_file_budget(ROOT / "tests", {".py"}, max_lines=350, max_bytes=16_000)
    _check_file_budget(ROOT / "tools", {".py"}, max_lines=350, max_bytes=16_000)
    _check_file_budget(ROOT / "apps/web/e2e", {".ts"}, max_lines=350, max_bytes=16_000)
    _check_file_budget(ROOT / "apps/web/acceptance", {".mjs"}, max_lines=350, max_bytes=16_000)
    _check_file_budget(ROOT / "apps/api/migrations", {".py"}, max_lines=350, max_bytes=16_000)


def test_frontend_http_is_centralized():
    for path in (ROOT / "apps/web/src").rglob("*.tsx"):
        assert not re.search(r"\bfetch\s*\(", path.read_text(encoding="utf-8")), path


def test_only_web_port_is_published_and_network_is_private():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert compose.count("ports:") == 1
    assert "127.0.0.1:${IZO_HTTP_PORT:-8080}:8080" in compose
    assert "internal: true" in compose
    assert "condition: service_completed_successfully" in compose
    assert "condition: service_healthy" in compose


def test_no_production_deploy_or_self_hosted_ci():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "pull_request_target" not in ci
    assert "self-hosted" not in ci
    assert "contents: read" in ci
    assert "secrets." not in ci


def test_dependency_lock_matches_web_manifest():
    manifest = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8"))
    assert lock["lockfileVersion"] == 3
    for group in ("dependencies", "devDependencies"):
        assert lock["packages"][""][group] == manifest[group]
        for name, version in manifest[group].items():
            assert lock["packages"]["node_modules/" + name]["version"] == version


def test_dependency_lock_is_required_not_bootstrapped_in_ci():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "infra/web.Dockerfile").read_text(encoding="utf-8")
    assert "npm install" not in ci
    assert "npm install" not in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "-r requirements-dev.txt" in ci
    assert "-r requirements.lock" in (ROOT / "infra/api.Dockerfile").read_text(encoding="utf-8")
