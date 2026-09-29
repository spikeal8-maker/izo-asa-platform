"""Foundation CI must retain the PLAN-approved Git base needed by history checks."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _approved_base() -> str:
    plan = json.loads((ROOT / "docs/PLAN.json").read_text(encoding="utf-8"))
    return plan["canonical_lineage"]["current_package_base"]["sha"]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )


def test_foundation_checkout_fetches_full_history():
    lines = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8").splitlines()
    checkout = [i for i, line in enumerate(lines) if "uses: actions/checkout@" in line]
    assert len(checkout) == 1
    block = "\n".join(lines[checkout[0] : checkout[0] + 5])
    assert re.search(r"\bfetch-depth:\s*0\b", block), block


def test_plan_approved_base_is_full_sha():
    assert FULL_SHA.fullmatch(_approved_base())


def test_approved_base_object_and_ancestry_are_available():
    base = _approved_base()
    shallow = _git("rev-parse", "--is-shallow-repository")
    assert shallow.returncode == 0, shallow.stderr
    assert shallow.stdout.strip() == "false"

    exists = _git("cat-file", "-e", f"{base}^{{commit}}")
    assert exists.returncode == 0, exists.stderr

    ancestor = _git("merge-base", "--is-ancestor", base, "HEAD")
    assert ancestor.returncode == 0, ancestor.stderr
