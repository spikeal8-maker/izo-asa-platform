"""Provider migration and secret/egress isolation boundaries."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_provider_migration_is_forward_only_and_has_no_application_imports():
    path = ROOT / "apps/api/migrations/versions/0009_provider_calls.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert not any(isinstance(node, ast.ImportFrom) and "izo" in (node.module or "")
                   for node in ast.walk(tree))
    text = path.read_text(encoding="utf-8")
    assert 'down_revision = "0008_jobs"' in text and "generation_provider_calls" in text
    assert "raise RuntimeError" in text


def test_fal_worker_secret_scope_and_egress_are_isolated_to_provider_service():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert sum(line.lstrip().startswith("IZO_FAL_KEY:") for line in compose.splitlines()) == 1
    assert "command: [python, '-m', izo.jobs.fal_worker]" in compose
    fal = compose[compose.index("  fal-worker:"):compose.index("  web:")]
    api = compose[compose.index("  api:"):compose.index("  job-worker:")]
    assert "provider-egress" in fal and "IZO_FAL_KEY" in fal
    assert "provider-egress" not in api and "IZO_FAL_KEY" not in api
