"""REST required-check proof and compatibility with historical checkpoint provenance."""
from __future__ import annotations

from copy import deepcopy

import pytest

from state_transport_fixtures import BASE, HEAD, JOBS, MERGE, NUMBER, REPO, TESTED, data_set, make_client
import project_state_connector as connector
from project_state_evidence import _workflow_pages, latest_required_runs, validate_pr_rollup
from project_state_rest_checks import collect


def proof_case(tmp_path):
    client, broker = make_client(tmp_path)
    proof = collect(client, NUMBER)
    pr = deepcopy(proof["pr"])
    selected = latest_required_runs(_workflow_pages([broker.data[f"repos/{REPO}/actions/runs"]]), HEAD, NUMBER)
    return pr, selected, proof


def test_real_protection_app_and_exact_attempt_replace_no_graphql_fields(tmp_path):
    pr, selected, proof = proof_case(tmp_path)
    validate_pr_rollup(NUMBER, pr, selected, proof, JOBS)
    assert "statusCheckRollup" not in proof
    assert "isRequired" not in str(proof)


@pytest.mark.parametrize("mode", ["wrong-pr", "wrong-head", "wrong-base", "wrong-head-name",
    "not-protected", "not-enabled", "not-enforced", "ruleset", "missing-context", "missing-check",
    "missing-app", "wrong-app", "pending-check", "failed-extra-check", "missing-page",
    "duplicate-check", "wrong-check-head", "legacy-failed", "legacy-pending", "legacy-wrong-head",
    "wrong-run", "wrong-path", "wrong-event", "wrong-workflow-id", "wrong-attempt", "wrong-suite",
    "wrong-job-run", "wrong-job-attempt", "wrong-job-check", "missing-job", "duplicate-job",
    "suite-cap", "missing-suite", "foreign-suite-head", "required-suite-pending"])
def test_required_check_proof_fails_closed(tmp_path, mode):
    pr, selected, proof = proof_case(tmp_path)
    protection = proof["branch"]["protection"]
    required = protection["required_status_checks"]
    checks = proof["check_pages"][0]
    bundle = proof["workflows"]["Foundation CI"]
    if mode == "wrong-pr": proof["pr"]["number"] += 1
    elif mode == "wrong-head": proof["pr"]["headRefOid"] = TESTED
    elif mode == "wrong-base": proof["pr"]["baseRefOid"] = TESTED
    elif mode == "wrong-head-name": proof["pr"]["headRefName"] = "other"
    elif mode == "not-protected": proof["branch"]["protected"] = False
    elif mode == "not-enabled": protection["enabled"] = False
    elif mode == "not-enforced": required["enforcement_level"] = "non_admins"
    elif mode == "ruleset": proof["rulesets"] = [{"id": 1, "enforcement": "active"}]
    elif mode == "missing-context": required["contexts"].pop()
    elif mode == "missing-check": required["checks"].pop()
    elif mode == "missing-app": required["checks"][0]["app_id"] = None
    elif mode == "wrong-app": checks["check_runs"][0]["app"]["id"] = 99
    elif mode == "pending-check": checks["check_runs"][0]["status"] = "in_progress"
    elif mode == "failed-extra-check":
        checks["check_runs"].append(dict(checks["check_runs"][0], id=999, name="Other", conclusion="failure"))
        checks["total_count"] += 1
    elif mode == "missing-page": checks["total_count"] += 1
    elif mode == "duplicate-check": checks["check_runs"][1]["id"] = checks["check_runs"][0]["id"]
    elif mode == "wrong-check-head": checks["check_runs"][0]["head_sha"] = TESTED
    elif mode.startswith("legacy-"):
        status = proof["status_pages"][0]
        if mode == "legacy-wrong-head": status["sha"] = TESTED
        else:
            status.update(total_count=1, state="success", statuses=[{"id": 999, "context": "external",
                "state": "failure" if mode == "legacy-failed" else "pending"}])
    elif mode == "wrong-run": bundle["run"]["id"] = 99
    elif mode == "wrong-path": bundle["run"]["path"] = ".github/workflows/pretend.yml"
    elif mode == "wrong-event": bundle["run"]["event"] = "workflow_dispatch"
    elif mode == "wrong-workflow-id": bundle["run"]["workflow_id"] = None
    elif mode == "wrong-attempt": bundle["run"]["run_attempt"] += 1
    elif mode == "wrong-suite": checks["check_runs"][0]["check_suite"]["id"] = 999
    elif mode == "wrong-job-run": bundle["jobs"][0]["run_id"] = 12
    elif mode == "wrong-job-attempt": bundle["jobs"][0]["run_attempt"] += 1
    elif mode == "wrong-job-check": bundle["jobs"][0]["check_run_url"] += "bad"
    elif mode == "missing-job": bundle["jobs"].pop()
    elif mode == "duplicate-job": bundle["jobs"].append(deepcopy(bundle["jobs"][0]))
    elif mode == "suite-cap": proof["suite_pages"][0]["total_count"] = 1000
    elif mode == "missing-suite": proof["suite_pages"][0]["check_suites"].pop()
    elif mode == "foreign-suite-head": proof["suite_pages"][0]["check_suites"][0]["head_sha"] = TESTED
    elif mode == "required-suite-pending": proof["suite_pages"][0]["check_suites"][0]["status"] = "queued"
    with pytest.raises(ValueError):
        validate_pr_rollup(NUMBER, pr, selected, proof, JOBS)


def test_foreign_queued_suite_with_no_actual_check_context_does_not_invent_a_pending_check(tmp_path):
    pr, selected, proof = proof_case(tmp_path)
    page = proof["suite_pages"][0]
    page["check_suites"].append({"id": 999, "head_sha": HEAD, "app": {"id": 999},
                                "status": "queued", "conclusion": None})
    page["total_count"] += 1
    validate_pr_rollup(NUMBER, pr, selected, proof, JOBS)


def test_historical_source_checkpoint_allows_main_to_advance_with_preserved_provenance(tmp_path):
    from project_state_merged_evidence import authenticate_initial_checkpoint
    data = data_set()
    data[f"repos/{REPO}/branches/main"]["commit"]["sha"] = "f" * 40
    data[f"repos/{REPO}/pulls/{NUMBER}/reviews"] = [{"id": 99, "state": "APPROVED", "commit_id": HEAD,
        "submitted_at": "2026-10-01T11:45:00Z", "user": {"login": "reviewer"}}]
    client, _ = make_client(tmp_path, data=data)
    checkpoint = {"type": "pr_merge_tree", "source_head": HEAD, "verified_pr": NUMBER, "base_head": BASE,
        "tested_merge_tree": TESTED, "workflows": {"Foundation CI": 11, "Dependency Security": 12, "Review Source": 13},
        "owner_waiver": False, "independent_review": "approved", "independent_review_source": HEAD,
        "independent_review_actor": "reviewer", "independent_review_id": 99}
    token = connector._ACTIVE.set(client)
    try:
        result = authenticate_initial_checkpoint(checkpoint,
            {"createdAt": "2026-10-01T12:30:00Z", "mergedAt": "2026-10-01T13:00:00Z"},
            REPO, introduced_at="2026-10-01T12:40:00Z", root=tmp_path)
        assert result == {"checkpoint_pr": NUMBER, "checkpoint_waiver_comment_id": None}
    finally:
        connector._ACTIVE.reset(token)


def test_merged_source_bootstrap_still_requires_exact_main(tmp_path, monkeypatch):
    import project_state_merged_source as source
    client, broker = make_client(tmp_path)
    pr = client.pr(NUMBER)
    runs = _workflow_pages([broker.data[f"repos/{REPO}/actions/runs"]])
    monkeypatch.setattr(source, "git", lambda *a, **k: f"{'f' * 40}\trefs/heads/main")
    with pytest.raises(ValueError, match="canonical main"):
        source.validate_merged_source_pr(NUMBER, HEAD, pr, runs, REPO, root=tmp_path)


def test_open_pr_path_requires_the_same_real_protection(tmp_path, monkeypatch):
    import project_state_evidence as evidence
    data = data_set()
    data[f"repos/{REPO}/pulls/{NUMBER}"].update(state="open", merged=False, merged_at=None)
    data[f"repos/{REPO}/branches/main"]["protection"]["required_status_checks"]["checks"] = []
    client, _ = make_client(tmp_path, data=data)
    monkeypatch.setattr(evidence, "repo_slug", lambda root: REPO)
    token = connector._ACTIVE.set(client)
    try:
        with pytest.raises(ValueError, match="protection contexts"):
            evidence.fetch_pr_evidence(NUMBER, HEAD, root=tmp_path)
    finally:
        connector._ACTIVE.reset(token)
