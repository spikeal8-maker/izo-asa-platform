"""Complete pagination, exact run/log identity and unchanged review predicates."""
from __future__ import annotations

from copy import deepcopy

import pytest

from state_transport_fixtures import HEAD, MERGE, NUMBER, REPO, TESTED, data_set, make_client
import project_state_connector as connector
from project_state_evidence import (_flatten_pages, _workflow_pages, foundation_tested_sha,
                                    latest_required_runs, fetch_review_evidence)
from project_state_provenance import _closeout_owner_waiver

PREFIX = f"repos/{REPO}"


def test_second_page_latest_failed_attempt_cannot_be_hidden_by_old_success():
    data = data_set()
    old = deepcopy(data[f"{PREFIX}/actions/runs"]["workflow_runs"])
    filler = [dict(old[0], id=100 + i, name=f"Other {i}") for i in range(97)]
    later = dict(old[0], id=999, run_attempt=2, run_number=4, conclusion="failure")
    data[f"{PREFIX}/actions/runs"] = {"total_count": 101, "workflow_runs": old + filler + [later]}
    client, broker = make_client(data=data)
    pages = client.get(f"{PREFIX}/actions/runs?event=pull_request&head_sha={HEAD}", paginate=True)
    assert len(pages) == 2 and "page=2" in broker.requests[-1]["params"]["endpoint"]
    with pytest.raises(ValueError, match="latest required workflow"):
        latest_required_runs(_workflow_pages(pages), HEAD, NUMBER)


@pytest.mark.parametrize("mode", ["missing-items", "wrong-collection", "no-total", "duplicate-id",
                                   "cap-boundary", "error", "wrong-shape"])
def test_incomplete_or_ambiguous_object_pagination_is_rejected(mode):
    def mutate(response, _):
        value = response["payload"]
        if mode == "missing-items": value["total_count"] += 1
        elif mode == "wrong-collection": value["jobs"] = value.pop("workflow_runs")
        elif mode == "no-total": value.pop("total_count")
        elif mode == "duplicate-id": value["workflow_runs"][1]["id"] = value["workflow_runs"][0]["id"]
        elif mode == "cap-boundary": value["total_count"] = 1000
        elif mode == "error": response["payload"] = {"message": "Forbidden"}
        elif mode == "wrong-shape": response["payload"] = []
        return response
    client, _ = make_client(mutate=mutate)
    with pytest.raises(ValueError, match="pagination"):
        client.get(f"{PREFIX}/actions/runs", paginate=True)


def test_list_pagination_reaches_page_two_and_terminating_page():
    data = data_set()
    data[f"{PREFIX}/pulls/{NUMBER}/reviews"] = [{"id": i} for i in range(200)]
    client, broker = make_client(data=data)
    pages = client.get(f"{PREFIX}/pulls/{NUMBER}/reviews", paginate=True)
    assert len(_flatten_pages(pages)) == 200 and len(broker.requests) == 3
    assert pages[-1] == []


@pytest.mark.parametrize("mode", ["wrong-sha", "empty-branch", "wrong-repo", "wrong-base",
                                   "wrong-url", "not-merged", "open-merged", "unknown-state"])
def test_pr_normalization_rejects_mixed_identity(mode):
    data = data_set()
    pr = data[f"{PREFIX}/pulls/{NUMBER}"]
    if mode == "wrong-sha": pr["head"]["sha"] = "a" * 39
    elif mode == "empty-branch": pr["head"]["ref"] = ""
    elif mode == "wrong-repo": pr["base"]["repo"]["full_name"] = "other/repo"
    elif mode == "wrong-base": pr["base"]["ref"] = "other"
    elif mode == "wrong-url": pr["html_url"] = "https://github.com/other/repo/pull/7"
    elif mode == "not-merged": pr["merged"] = False
    elif mode == "open-merged": pr["state"] = "open"
    elif mode == "unknown-state": pr["state"] = "unknown"
    client, _ = make_client(data=data)
    with pytest.raises(ValueError, match="identity"):
        client.pr(NUMBER)


def test_immutable_commit_cannot_use_the_body_of_another_sha():
    data = data_set()
    data[f"{PREFIX}/commits/{MERGE}"]["sha"] = TESTED
    client, _ = make_client(data=data)
    with pytest.raises(ValueError, match="immutable commit SHA"):
        client.get(f"{PREFIX}/commits/{MERGE}")


@pytest.mark.parametrize("mode", ["success", "two-builds", "missing-log", "wrong-attempt", "wrong-run",
                                   "wrong-check", "wrong-head", "missing-page", "run-changed"])
def test_foundation_build_is_read_from_full_logs_of_exact_selected_attempt(tmp_path, mode):
    data = data_set()
    jobs = data[f"{PREFIX}/actions/runs/11/jobs"]
    if mode == "two-builds": data["log:111"] += f"IZO_BUILD_SHA: {MERGE}\n"
    elif mode == "missing-log": data["log:111"] = ""
    elif mode == "wrong-attempt": jobs["jobs"][0]["run_attempt"] = 2
    elif mode == "wrong-run": jobs["jobs"][0]["run_id"] = 12
    elif mode == "wrong-check": jobs["jobs"][0]["check_run_url"] += "999"
    elif mode == "wrong-head": jobs["jobs"][0]["head_sha"] = TESTED
    elif mode == "missing-page": jobs["total_count"] = 101
    client, _ = make_client(tmp_path, data=data)
    client.get(f"{PREFIX}/actions/runs", paginate=True)
    if mode == "run-changed":
        data[f"{PREFIX}/actions/runs/11"]["check_suite_id"] += 1
    token = connector._ACTIVE.set(client)
    try:
        if mode == "success":
            assert foundation_tested_sha(11, REPO, root=tmp_path) == TESTED
            assert TESTED != HEAD and TESTED != MERGE
        else:
            with pytest.raises(ValueError):
                foundation_tested_sha(11, REPO, root=tmp_path)
    finally:
        connector._ACTIVE.reset(token)


@pytest.mark.parametrize("verdict", ["CHANGES_REQUESTED", "DISMISSED"])
def test_page_two_review_revokes_page_one_approval(tmp_path, monkeypatch, verdict):
    data = data_set()
    approved = {"id": 1, "state": "APPROVED", "commit_id": HEAD,
                "submitted_at": "2026-10-01T11:30:00Z", "user": {"login": "reviewer"}}
    irrelevant = [{"id": i, "state": "COMMENTED", "user": {"login": f"other{i}"}}
                  for i in range(2, 101)]
    revoked = dict(approved, id=101, state=verdict, submitted_at="2026-10-01T11:40:00Z")
    data[f"{PREFIX}/pulls/{NUMBER}/reviews"] = [approved, *irrelevant, revoked]
    client, _ = make_client(tmp_path, data=data)
    import project_state_evidence as evidence
    monkeypatch.setattr(evidence, "repo_slug", lambda root: REPO)
    token = connector._ACTIVE.set(client)
    try:
        with pytest.raises(ValueError):
            fetch_review_evidence({"risk": "high"}, NUMBER, HEAD, root=tmp_path)
    finally:
        connector._ACTIVE.reset(token)


@pytest.mark.parametrize("edited", [False, True])
def test_real_source_waiver_on_second_page_must_precede_merge(tmp_path, edited):
    data = data_set()
    comment = {"id": 101, "user": {"login": "owner"}, "author_association": "OWNER",
        "created_at": "2026-10-01T11:40:00Z",
        "updated_at": "2026-10-01T12:01:00Z" if edited else "2026-10-01T11:40:00Z",
        "body": (f"Owner waiver for source checkpoint PR #{NUMBER}: APPROVE\nSource HEAD: {HEAD}\n"
                 "Independent review: unavailable\nReason: Reviewer unavailable.\nFoundation CI: 11 SUCCESS\n"
                 "Dependency Security: 12 SUCCESS\nReview Source: 13 SUCCESS")}
    data[f"{PREFIX}/issues/{NUMBER}/comments"] = [{"id": i} for i in range(100)] + [comment]
    client, _ = make_client(tmp_path, data=data)
    token = connector._ACTIVE.set(client)
    try:
        result = _closeout_owner_waiver(NUMBER, HEAD,
            {"Foundation CI": 11, "Dependency Security": 12, "Review Source": 13},
            "2026-10-01T12:00:00Z", REPO, root=tmp_path, source_checkpoint=True)
        assert result == (None if edited else ("Reviewer unavailable.", 101))
    finally:
        connector._ACTIVE.reset(token)
