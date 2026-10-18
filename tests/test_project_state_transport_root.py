"""Real isolated Git checkouts exercise CLI root routing and the last mutation fence."""
from __future__ import annotations

import json
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys

import pytest

from state_transport_fixtures import (HEAD, MERGE, NUMBER, REPO, TESTED, checkout,
    data_set, git, make_client, source_waiver_comment, state_bytes)
import project_state as state
import project_state_closeout as closeout
import project_state_connector as connector
import project_state_evidence as evidence
import project_state_merged_source as merged

TOOL_ROOT = Path(__file__).resolve().parents[1]


def execute_case(tmp_path, monkeypatch, mode, command):
    root = tmp_path / "target"
    plan, source = checkout(root, decided=command != "begin-next")
    originals, tooling_originals = state_bytes(root), state_bytes(TOOL_ROOT)
    data = json.loads(json.dumps(data_set()).replace(HEAD, source).replace("codex/test-package", "source"))
    data[f"repos/{REPO}/pulls/{NUMBER}/reviews"] = [{"id": 99, "state": "APPROVED", "commit_id": source,
        "submitted_at": "2026-10-01T11:45:00Z", "user": {"login": "reviewer"}}]
    if mode == "owner-waiver":
        data[f"repos/{REPO}/pulls/{NUMBER}/reviews"] = []
        data[f"repos/{REPO}/issues/{NUMBER}/comments"] = [source_waiver_comment(source)]
    if mode == "no-review": data[f"repos/{REPO}/pulls/{NUMBER}/reviews"] = []
    if mode == "late-review":
        data[f"repos/{REPO}/pulls/{NUMBER}/reviews"][0]["submitted_at"] = "2026-10-01T12:01:00Z"
    if mode.startswith("open-"):
        data[f"repos/{REPO}/pulls/{NUMBER}"].update(state="open", merged=False, merged_at=None, merge_commit_sha=TESTED)
    if mode == "wrong-source": data[f"repos/{REPO}/pulls/{NUMBER}"]["head"]["sha"] = HEAD
    if mode == "ruleset": data[f"repos/{REPO}/rulesets"] = [{"id": 9, "enforcement": "active"}]
    if mode == "dirty": (root / "marker.txt").write_text("owner changes")
    if mode == "wrong-branch": git(root, "switch", "other")
    mutated, branch_reads, review_reads = False, 0, 0
    def mutate(response, request):
        nonlocal mutated, branch_reads, review_reads
        endpoint = request["params"].get("endpoint", "")
        if mode == "eof": return ""
        if mode == "nonce": response["nonce"] = "another-session"
        if "/issues/" in endpoint and not mutated:
            mutated = True
            if mode == "dirty-during": (root / "marker.txt").write_text("concurrent change")
            elif mode == "head-during": git(root, "commit", "--quiet", "--allow-empty", "-m", "Concurrent owner commit")
            elif mode == "branch-during": git(root, "switch", "other")
        if "/reviews?" in endpoint:
            review_reads += 1
            if mode == "origin-during" and review_reads == 2:
                git(root, "remote", "set-url", "origin", "https://github.com/other/repo.git")
        if endpoint.endswith("/branches/main"):
            branch_reads += 1
            if mode == "stale-github" and branch_reads == 2:
                response["payload"]["protection"]["enabled"] = False
        return response
    client, broker = make_client(root, data=data, mutate=mutate)
    monkeypatch.setattr(connector, "LiveBridge", lambda repo: client.bridge)
    original_git, remote_reads, mutations = state.git, 0, []
    def local_git(*args, root):
        nonlocal remote_reads
        assert root.resolve() == client.root
        if args[0] == "ls-remote":
            remote_reads += 1
            sha = MERGE if args[-1] == "refs/heads/main" else TESTED
            if mode in {"main-drift", "open-merge-drift"} and remote_reads == 2:
                sha = "f" * 40
            return f"{sha}\t{args[-1]}"
        if args[:2] == ("switch", "-c"):
            mutations.append(args)
        return original_git(*args, root=root)
    for module in (state, closeout, evidence, merged):
        monkeypatch.setattr(module, "git", local_git)
    runner = closeout if command == "complete" else state
    argv = [runner.__file__, "--repo-root", str(root), "--github-transport", "connector-stdio"]
    if command != "complete": argv += [command, "--activate", "TEST-TRANSPORT-NEXT"]
    argv += ["--branch", "test/next", "--verified-pr", str(NUMBER)]
    if command == "begin-decided-next":
        argv += ["--goal", "Bounded synthetic transport fixture", "--depends-on", plan["active_package"], "--decides-next"]
    if mode == "merged-waiver-flags":
        argv += ["--owner-waiver", "--independent-review-unavailable", "--owner-waiver-source", source,
                 "--owner-waiver-reason", "Cannot create a post-merge waiver"]
    monkeypatch.setattr(sys, "argv", argv)
    errors = StringIO()
    with redirect_stderr(errors):
        result = runner.main()
    expected_error = {"dirty": "clean checkout", "wrong-branch": "current working_branch",
        "wrong-source": "identity", "eof": "missing, truncated", "nonce": "identity",
        "ruleset": "without rulesets", "dirty-during": "checkout changed", "head-during": "checkout changed",
        "branch-during": "checkout changed", "origin-during": "origin changed", "stale-github": "changed before state mutation",
        "main-drift": "merge ref changed", "open-merge-drift": "merge ref changed",
        "no-review": "requires structured", "late-review": "must precede",
        "merged-waiver-flags": "reuse authenticated pre-merge evidence"}.get(mode)
    if expected_error:
        assert expected_error in errors.getvalue(), errors.getvalue()
    else:
        assert result == 0, errors.getvalue()
    assert state_bytes(TOOL_ROOT) == tooling_originals
    return result, root, originals, mutations, broker


@pytest.mark.parametrize("command", ["begin-next", "begin-decided-next", "complete"])
@pytest.mark.parametrize("mode", ["success", "owner-waiver"])
def test_reviewed_tooling_can_transition_only_explicit_target_checkout(tmp_path, monkeypatch, command, mode):
    result, root, originals, mutations, broker = execute_case(tmp_path, monkeypatch, mode, command)
    assert result == 0 and len(mutations) == 1
    assert git(root, "branch", "--show-current") == "test/next"
    updated = state.load_plan(root)
    if command == "complete":
        original = json.loads(originals["PLAN.json"])
        active = original["active_package"]
        assert updated["active_package"] == active and updated["next_package"] is None
        assert updated["packages"][active]["status"] == "complete"
        assert updated["canonical_lineage"] == original["canonical_lineage"]
        checkpoint = state.load_checkpoints(root)["checkpoints"][active]
        assert checkpoint["source_head"] == git(root, "rev-parse", "HEAD")
        if mode == "owner-waiver":
            assert checkpoint["source_waiver_comment_id"] == 77
            assert checkpoint["owner_actor"] == "owner"
            assert checkpoint["owner_waiver_source"] == checkpoint["source_head"]
        else:
            assert checkpoint["independent_review"] == "approved"
    else:
        assert updated["active_package"] == "TEST-TRANSPORT-NEXT"
    assert state_bytes(root) != originals
    assert len([row for row in broker.requests if row["params"].get("endpoint", "").endswith("/branches/main")]) == 2


@pytest.mark.parametrize("command", ["begin-next", "begin-decided-next", "complete"])
@pytest.mark.parametrize("mode", ["dirty", "wrong-branch", "wrong-source", "eof", "nonce", "ruleset",
                                   "dirty-during", "head-during", "branch-during", "origin-during", "stale-github",
                                   "main-drift", "no-review", "late-review", "merged-waiver-flags"])
def test_failure_before_commit_barrier_preserves_all_state_and_creates_no_branch(tmp_path, monkeypatch, mode, command):
    result, root, originals, mutations, _ = execute_case(tmp_path, monkeypatch, mode, command)
    assert result == 2 and mutations == []
    assert state_bytes(root) == originals
    assert git(root, "branch", "--format=%(refname:short)").splitlines() == ["other", "source"]


@pytest.mark.parametrize("mode,expected", [("open-success", 0), ("open-merge-drift", 2)])
@pytest.mark.parametrize("command", ["begin-decided-next", "complete"])
def test_open_pr_rechecks_tested_merge_git_ref_after_rest_freshness(tmp_path, monkeypatch, mode, expected, command):
    result, root, originals, mutations, _ = execute_case(tmp_path, monkeypatch, mode, command)
    assert result == expected
    if expected == 2:
        assert mutations == [] and state_bytes(root) == originals


def test_mixed_root_and_subdirectory_are_rejected_without_github_or_state_io(tmp_path):
    root = tmp_path / "target"
    checkout(root)
    originals = state_bytes(root)
    client, broker = make_client(root)
    token = connector._ACTIVE.set(client)
    try:
        with pytest.raises(ValueError, match="mix repository roots"):
            evidence.github_api(f"repos/{REPO}/branches/main", root=tmp_path)
    finally:
        connector._ACTIVE.reset(token)
    with pytest.raises(ValueError, match="exact checkout root"):
        with connector.transport("connector-stdio", root / "docs"):
            pytest.fail("subdirectory must not select a transport")
    assert broker.requests == [] and state_bytes(root) == originals


def test_completed_closeout_rechecks_main_before_writing(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path)
    token = connector._ACTIVE.set(client)
    monkeypatch.setattr(evidence, "repo_slug", lambda root: REPO)
    try:
        with pytest.raises(ValueError, match="main or tested PR merge ref changed"):
            connector.before_write(HEAD, "source", {"type": "completed_merged_closeout", "source_head": MERGE},
                tmp_path, git_fn=lambda *a, **k: f"{'f' * 40}\trefs/heads/main")
    finally:
        connector._ACTIVE.reset(token)


def test_closeout_cli_defaults_to_gh_and_routes_all_state_to_explicit_root(tmp_path, monkeypatch):
    target = tmp_path / "target"
    plan, source = checkout(target)
    tooling_originals = state_bytes(TOOL_ROOT)
    def collect(pr, head, *, root):
        assert (pr, head, root) == (NUMBER, source, target)
        return {"type": "pr_merge_tree", "source_head": source, "tested_merge_tree": TESTED}
    def review(*args, root, **kwargs):
        assert root == target
        return {"independent_review": "approved", "owner_waiver": False}
    monkeypatch.setattr(closeout, "fetch_pr_evidence", collect)
    monkeypatch.setattr(closeout, "fetch_review_evidence", review)
    monkeypatch.setattr(connector, "LiveBridge", lambda *args: pytest.fail("default gh opened Connector"))
    monkeypatch.setattr(sys, "argv", [closeout.__file__, "--repo-root", str(target),
        "--branch", "state/complete", "--verified-pr", str(NUMBER)])
    assert closeout.main() == 0
    assert git(target, "branch", "--show-current") == "state/complete"
    assert state.load_plan(target)["packages"][plan["active_package"]]["status"] == "complete"
    assert state_bytes(TOOL_ROOT) == tooling_originals
