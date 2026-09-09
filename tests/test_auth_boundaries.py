"""Auth scope invariants and additive environment bootstrap regression checks."""
from pathlib import Path
import re

from tools.bootstrap import add_auth_settings, bootstrap

ROOT = Path(__file__).resolve().parents[1]


def test_accounts_do_not_depend_on_generation_credits_or_demo():
    for path in (ROOT / "apps/api/izo/accounts").glob("*.py"):
        imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", path.read_text(), re.MULTILINE)
        assert not any(any(x in name for x in ("generation", "credits", "prototype", "providers")) for name in imports), path


def test_client_auth_never_uses_local_storage_as_identity():
    for path in (ROOT / "apps/web/src/features/accounts").glob("*.tsx"):
        text = path.read_text()
        assert "sessionStorage" not in text and "localStorage" not in text
        assert not re.search(r"\bfetch\s*\(", text)
        assert "useDemo" not in text


def test_auth_changes_have_a_real_postgres_restart_gate():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "tools/auth_acceptance.py before" in workflow
    assert "tools/auth_acceptance.py after" in workflow
    assert "umask 077" in workflow
    assert "IZO_AUTH_ACCEPTANCE=isolated" in workflow
    assert workflow.index("tools/auth_acceptance.py before") < workflow.index("docker compose down\n")
    assert workflow.index("tools/auth_acceptance.py after") > workflow.index("docker compose up --wait")


def test_bootstrap_upgrade_is_additive_and_idempotent(tmp_path):
    path = tmp_path / ".env"
    before = "IZO_PG_PASSWORD=keep-existing\nIZO_S3_SECRET_KEY=also-keep"
    path.write_text(before)
    assert add_auth_settings(path)
    after = path.read_text()
    assert after.startswith(before + "\n")
    assert "IZO_AUTH_RATE_SECRET=" in after
    assert "IZO_AUTH_REGISTRATION=invite" in after
    assert not add_auth_settings(path)
    assert path.read_text() == after


def test_bootstrap_never_replaces_auth_secret_or_mode(tmp_path):
    path = tmp_path / ".env"
    before = "IZO_AUTH_RATE_SECRET=existing\nIZO_AUTH_REGISTRATION=disabled\n"
    path.write_text(before)
    assert not add_auth_settings(path)
    assert path.read_text() == before


def test_new_bootstrap_includes_auth_without_recreating_secrets(tmp_path):
    path = tmp_path / ".env"
    assert bootstrap(path)
    before = path.read_bytes()
    assert not bootstrap(path) and not add_auth_settings(path)
    assert path.read_bytes() == before


def test_openapi_matches_public_password_and_redacted_error_contract():
    from izo.app import create_app
    from izo.config import Settings
    document = create_app(Settings()).openapi()
    assert document["components"]["schemas"]["RegisterInput"]["properties"]["password"]["minLength"] == 15
    for path, operations in document["paths"].items():
        if path.startswith("/api/v1/auth/"):
            for operation in operations.values():
                schema = operation["responses"]["422"]["content"]["application/json"]["schema"]
                assert schema == {"$ref": "#/components/schemas/AuthErrorView"}
