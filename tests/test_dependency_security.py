"""Keep the separate dependency gate honest; no registry or package install here."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/dependency-audit.yml"


def test_npm_audit_includes_build_dependencies_and_fails_on_high():
    text = WORKFLOW.read_text(encoding="utf-8")
    command = next(line.strip() for line in text.splitlines() if "run: npm audit " in line)
    assert "--audit-level=high" in command
    assert "--include=dev" in command
    assert "--include=optional" in command
    assert "--include=peer" in command
    assert "--json" in command
    assert "--registry=https://registry.npmjs.org" in command
    assert "--omit" not in command
    assert "||" not in command and ";" not in command
    assert "continue-on-error" not in text


def test_security_runner_has_no_secrets_write_token_or_unreviewed_actions():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: read" in text
    assert "persist-credentials: false" in text
    assert "ubuntu-24.04" in text
    assert "node-version: '24'" in text
    for forbidden in ("secrets.", "pull_request_target", "self-hosted", "write-all", "contents: write"):
        assert forbidden not in text
    actions = re.findall(r"uses: ([^\s]+)", text)
    assert len(actions) == 3
    assert all(re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", action) for action in actions)


def test_audit_does_not_update_dependencies_or_execute_package_hooks():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "npm ci --ignore-scripts --no-audit --no-fund" in text
    for forbidden in ("audit fix", "npm update", "npm install", "git push", "git commit", "sec001-candidate"):
        assert forbidden not in text
    assert "node --test security/dependencies.test.mjs" in text
    assert (ROOT / "apps/web/security/dependencies.test.mjs").is_file()


def test_evidence_is_kept_on_failure_without_collecting_auth_fixtures():
    text = WORKFLOW.read_text(encoding="utf-8")
    artifact = text.split("      - name: Save audit evidence even on failure\n", 1)[1]
    assert "if: always()" in artifact
    assert "if-no-files-found: error" in artifact
    paths = artifact.split("path: |\n", 1)[1].split("retention-days:", 1)[0]
    assert "izo-dependency-audit.json" in paths
    assert "izo-dependency-versions.txt" in paths
    for forbidden in ("*", "izo-auth", "izo-email", "izo-credit", ".env", "node_modules"):
        assert forbidden not in paths
