"""Small, targeted AUTH-002 invariants, not a complete security scanner."""
from pathlib import Path
import re
from tools.bootstrap import add_recovery_settings, add_auth_settings, bootstrap

ROOT = Path(__file__).resolve().parents[1]


def test_recovery_upgrade_preserves_all_existing_configuration(tmp_path):
    path = tmp_path / ".env"
    original = "IZO_PG_PASSWORD=untouched\nIZO_AUTH_RATE_SECRET=also-untouched"
    path.write_text(original)
    assert add_recovery_settings(path)
    updated = path.read_text(encoding="utf-8")
    assert updated.startswith(original + "\n")
    assert "IZO_RECOVERY_SECRET=" in updated and "IZO_RECOVERY_DELIVERY=test" in updated
    assert not add_recovery_settings(path) and path.read_text(encoding="utf-8") == updated


def test_bootstrap_does_not_replace_disabled_recovery(tmp_path):
    path = tmp_path / ".env"
    value = "IZO_RECOVERY_SECRET=existing\nIZO_RECOVERY_DELIVERY=disabled\n"
    path.write_text(value)
    assert not add_recovery_settings(path) and path.read_text(encoding="utf-8") == value


def test_new_bootstrap_has_separate_secrets_and_preserves_auth_upgrade(tmp_path):
    path = tmp_path / ".env"
    assert bootstrap(path)
    values = dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#"))
    assert values["IZO_AUTH_RATE_SECRET"] != values["IZO_RECOVERY_SECRET"]
    assert not bootstrap(path) and not add_auth_settings(path) and not add_recovery_settings(path)


def test_recovery_sender_is_only_operator_test_mail():
    routes = (ROOT / "apps/api/izo/accounts/challenge_routes.py").read_text(encoding="utf-8")
    assert "test_mail" not in routes and "messages(" not in routes
    for name in ("challenges.py", "test_mail.py", "challenge_policy.py"):
        source = (ROOT / "apps/api/izo/accounts" / name).read_text(encoding="utf-8")
        assert not re.search(r"^\s*(?:from|import)\s+(smtplib|requests|httpx|urllib.request)", source, re.M)


def test_security_forms_do_not_store_proof_or_use_browser_identity():
    source = (ROOT / "apps/web/src/features/accounts/SecurityPage.tsx").read_text(encoding="utf-8")
    assert "localStorage" not in source and "sessionStorage" not in source
    assert not re.search(r"\bfetch\s*\(", source)
    assert "history.replaceState" in source
    assert 'name="referrer" content="no-referrer"' in (ROOT / "apps/web/index.html").read_text(encoding="utf-8")


def test_email_gate_surrounds_real_restart_without_replacing_auth_gate():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert text.index("tools/email_acceptance.py before") < text.index("docker compose down\n")
    assert text.index("tools/email_acceptance.py after") > text.index("docker compose up --wait")
    assert "tools/auth_acceptance.py before" in text and "tools/auth_acceptance.py after" in text
    assert 'rm -f "$RUNNER_TEMP/izo-email-proof.json"' in text
