"""Small executable architecture checks, not a new governance framework."""
import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

PROD_LIMITS = {
    ROOT / "apps/api/izo": ({".py"}, 300, 12_000),
    ROOT / "apps/web/src": ({".ts", ".tsx", ".css"}, 300, 12_000),
}
AUX_LIMITS = {
    ROOT / "tests": ({".py"}, 350, 16_000),
    ROOT / "tools": ({".py"}, 350, 16_000),
    ROOT / "apps/web/e2e": ({".ts"}, 350, 16_000),
    ROOT / "apps/web/acceptance": ({".mjs"}, 350, 16_000),
    ROOT / "apps/api/migrations": ({".py"}, 350, 16_000),
}


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
    for root, (suffixes, lines, size) in {**PROD_LIMITS, **AUX_LIMITS}.items():
        _check_file_budget(root, suffixes, max_lines=lines, max_bytes=size)


def _changed_paths(base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", base, "HEAD", "--"],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=True)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _old_blob_size(base: str, raw: str) -> int:
    result = subprocess.run(
        ["git", "show", f"{base}:{raw}"], cwd=ROOT, capture_output=True, timeout=20)
    return len(result.stdout) if result.returncode == 0 else 0


def _limit_for(path: Path):
    for root, (_, max_lines, max_bytes) in {**PROD_LIMITS, **AUX_LIMITS}.items():
        try:
            path.relative_to(root)
            return max_lines, max_bytes
        except ValueError:
            continue
    return None


def test_near_limit_changed_files_do_not_keep_growing():
    plan = json.loads((ROOT / "docs/PLAN.json").read_text(encoding="utf-8"))
    base = plan["canonical_lineage"]["current_package_base"]["sha"]
    for raw in _changed_paths(base):
        path = ROOT / raw
        limit = _limit_for(path)
        if not limit or not path.is_file() or ".generated." in path.name:
            continue
        _, max_bytes = limit
        new_size = path.stat().st_size
        old_size = _old_blob_size(base, raw)
        if new_size > int(max_bytes * 0.80):
            assert old_size and new_size <= old_size, (
                f"{raw} is above 80% of its {max_bytes}-byte hard limit and grew "
                f"{old_size}->{new_size}; split responsibility instead")


def test_ci_workflows_stay_modular():
    for path in (ROOT / ".github/workflows").glob("*.y*ml"):
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 350, path
        assert len(text.encode("utf-8")) <= 16_000, path


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
