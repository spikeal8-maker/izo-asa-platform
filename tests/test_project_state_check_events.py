"""Multiple-event REST checks: synthetic fixtures based on observed GitHub shapes."""
from __future__ import annotations

from copy import deepcopy

import pytest

from state_transport_fixtures import HEAD, JOBS, NUMBER, REPO, data_set, make_client
from project_state_evidence import _workflow_pages, latest_required_runs, validate_pr_rollup
from project_state_rest_checks import collect


def multiple_event_data(*, merged=False, detached=False, history_result="cancelled"):
    """Synthetic identities; the 3-event/12-check shape reproduces observed PR #271.

    The real filter=latest response retained one cancelled verify from an older
    event. This fixture is test data, never a substitute for live API evidence.
    """
    data = data_set()
    prefix = f"repos/{REPO}"
    if not merged:
        data[f"{prefix}/pulls/{NUMBER}"].update(state="open", merged=False, merged_at=None)
    templates = deepcopy(data)
    runs, checks, suites = [], [], []
    for event in (3, 2, 1):
        offset = event * 1000
        for template in templates[f"{prefix}/actions/runs"]["workflow_runs"]:
            old_id = template["id"]
            run = deepcopy(template)
            run.update(id=old_id + offset, check_suite_id=template["check_suite_id"] + offset,
                       run_number=event, created_at=f"2026-10-01T11:0{event}:00Z",
                       updated_at=f"2026-10-01T11:0{event}:50Z")
            if event == 2 and run["name"] == "Foundation CI":
                run.update(conclusion=history_result, updated_at="2026-10-01T11:03:01Z")
            if detached:
                run["pull_requests"] = []
            jobs = deepcopy(templates[f"{prefix}/actions/runs/{old_id}/jobs"]["jobs"])
            for job in jobs:
                job.update(id=job["id"] + offset, run_id=run["id"],
                           run_url=f"https://api.github.com/{prefix}/actions/runs/{run['id']}")
                job["check_run_url"] = f"https://api.github.com/{prefix}/check-runs/{job['id']}"
                if event == 2 and job["name"] == "verify":
                    job["conclusion"] = history_result
                checks.append({"id": job["id"], "name": job["name"], "head_sha": HEAD,
                    "status": job["status"], "conclusion": job["conclusion"], "app": {"id": 42},
                    "check_suite": {"id": run["check_suite_id"]},
                    "pull_requests": [] if detached else [{"number": NUMBER}],
                    "details_url": f"https://github.com/{REPO}/actions/runs/{run['id']}/job/{job['id']}"})
            runs.append(run)
            suites.append({"id": run["check_suite_id"], "head_sha": HEAD, "app": {"id": 42},
                           "status": "completed", "conclusion": run["conclusion"]})
            data[f"{prefix}/actions/runs/{run['id']}"] = run
            data[f"{prefix}/actions/runs/{run['id']}/jobs"] = {"total_count": len(jobs), "jobs": jobs}
    data[f"{prefix}/actions/runs"] = {"total_count": len(runs), "workflow_runs": runs}
    data[f"{prefix}/commits/{HEAD}/check-runs"] = {"total_count": len(checks), "check_runs": checks}
    data[f"{prefix}/commits/{HEAD}/check-suites"] = {"total_count": len(suites), "check_suites": suites}
    return data


@pytest.mark.parametrize("merged,detached", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("history_result", ["cancelled", "failure"])
def test_multiple_pr_events_keep_cancelled_history_and_accept_current_checks(
        tmp_path, merged, detached, history_result):
    data = multiple_event_data(merged=merged, detached=detached, history_result=history_result)
    client, _ = make_client(tmp_path, data=data)
    proof = collect(client, NUMBER)
    selected = latest_required_runs(_workflow_pages([data[f"repos/{REPO}/actions/runs"]]), HEAD, NUMBER,
                                   allow_detached=merged, expected_branch=proof["pr"]["headRefName"])
    original = deepcopy(proof)
    validate_pr_rollup(NUMBER, proof["pr"], selected, proof, JOBS)
    assert proof == original
    assert {row["databaseId"] for row in selected.values()} == {3011, 3012, 3013}
    assert proof["check_pages"] == [data[f"repos/{REPO}/commits/{HEAD}/check-runs"]]
    assert proof["run_pages"] == [data[f"repos/{REPO}/actions/runs"]]
    assert proof["check_pages"][0]["total_count"] == 12
    assert len(proof["historical_workflows"]) == 6
    assert any(row["conclusion"] == history_result for row in proof["check_pages"][0]["check_runs"])
    earlier = data[f"repos/{REPO}/actions/runs/2011"]
    current = data[f"repos/{REPO}/actions/runs/3011"]
    assert earlier["updated_at"] > current["created_at"]


def event_case(tmp_path):
    client, _ = make_client(tmp_path, data=multiple_event_data())
    proof = collect(client, NUMBER)
    pr = deepcopy(proof["pr"])
    selected = latest_required_runs(_workflow_pages(proof["run_pages"]), HEAD, NUMBER)
    return pr, selected, proof


@pytest.mark.parametrize("mode", ["workflow-id", "path", "head", "branch", "event", "repo", "pr",
    "missing-pr", "same-event", "same-event-new-attempt", "run-detail-drift", "stale-attempt",
    "job-run", "job-attempt", "job-head", "job-id", "job-url", "job-check-url", "check-id",
    "check-url", "check-pr", "missing-check-pr", "foreign-app", "foreign-suite", "pending-check",
    "pending-run", "pending-job", "pending-suite", "unknown-result", "duplicate-bundle",
    "duplicate-job", "missing-job", "unreported-job", "missing-bundle", "missing-run-page",
    "duplicate-run", "duplicate-suite", "unproven-failure", "unproven-success-duplicate",
    "suite-type", "app-type", "run-list-type", "unsupported-result"])
def test_history_cannot_hide_unproven_or_ambiguous_checks(tmp_path, mode):
    pr, selected, proof = event_case(tmp_path)
    bundle = next(row for row in proof["historical_workflows"] if row["run"]["id"] == 2011)
    run = bundle["run"]
    listed = next(row for row in proof["run_pages"][0]["workflow_runs"] if row["id"] == 2011)
    jobs = bundle["job_pages"][0]
    job = next(row for row in jobs["jobs"] if row["name"] == "verify")
    checks = proof["check_pages"][0]
    check = next(row for row in checks["check_runs"] if row["id"] == job["id"])
    suite = next(row for row in proof["suite_pages"][0]["check_suites"] if row["id"] == 2111)
    run_changes = {"workflow-id": ("workflow_id", 999), "path": ("path", ".github/workflows/other.yml"),
        "head": ("head_sha", "f" * 40), "branch": ("head_branch", "other"),
        "event": ("event", "workflow_dispatch"), "repo": ("repository", {"full_name": "other/repo"}),
        "pr": ("pull_requests", [{"number": NUMBER + 1}]), "missing-pr": ("pull_requests", []),
        "same-event": ("run_number", 3), "same-event-new-attempt": ("run_number", 3),
        "stale-attempt": ("run_attempt", 2), "pending-run": ("status", "in_progress")}
    if mode in run_changes:
        key, value = run_changes[mode]
        run[key] = listed[key] = value
        if mode == "same-event-new-attempt":
            run["run_attempt"] = listed["run_attempt"] = 2
    elif mode == "run-detail-drift": run["updated_at"] = "2026-10-01T11:04:00Z"
    elif mode.startswith("job-"):
        key, value = {"job-run": ("run_id", 3011), "job-attempt": ("run_attempt", 2),
            "job-head": ("head_sha", "f" * 40), "job-id": ("id", 999),
            "job-url": ("run_url", "https://example.invalid/run"),
            "job-check-url": ("check_run_url", "https://example.invalid/check")}[mode]
        job[key] = value
    elif mode == "check-id": check["id"] = 999
    elif mode == "check-url": check["details_url"] = "https://example.invalid/check"
    elif mode == "check-pr": check["pull_requests"] = [{"number": NUMBER + 1}]
    elif mode == "missing-check-pr": check.pop("pull_requests")
    elif mode == "foreign-app":
        suite["app"] = {"id": 999}
        for row in checks["check_runs"]:
            if row["check_suite"]["id"] == suite["id"]: row["app"] = {"id": 999}
    elif mode == "foreign-suite": check["check_suite"] = {"id": 2112}
    elif mode == "pending-check": check["status"] = "in_progress"
    elif mode == "pending-job": job["status"] = "in_progress"
    elif mode == "pending-suite": suite["status"] = "queued"
    elif mode == "unknown-result": check["conclusion"] = job["conclusion"] = "unrecognized"
    elif mode == "unsupported-result": check["conclusion"] = job["conclusion"] = "startup_failure"
    elif mode == "suite-type": check["check_suite"]["id"] = float(suite["id"])
    elif mode == "app-type": suite["app"]["id"] = 42.0
    elif mode == "run-list-type": listed["run_attempt"] = True
    elif mode == "duplicate-bundle": proof["historical_workflows"].append(deepcopy(bundle))
    elif mode == "duplicate-job":
        jobs["jobs"].append(deepcopy(job))
        jobs["total_count"] += 1
    elif mode == "missing-job": jobs["jobs"].pop()
    elif mode == "unreported-job":
        jobs["jobs"].remove(job)
        jobs["total_count"] -= 1
    elif mode == "missing-bundle": proof["historical_workflows"].remove(bundle)
    elif mode == "missing-run-page": proof["run_pages"][0]["total_count"] += 1
    elif mode == "duplicate-run":
        proof["run_pages"][0]["workflow_runs"].append(deepcopy(listed))
        proof["run_pages"][0]["total_count"] += 1
    elif mode == "duplicate-suite": listed["check_suite_id"] = 3111
    else:
        extra = dict(check, id=999, check_suite={"id": 999},
                     conclusion="failure" if mode == "unproven-failure" else "success")
        checks["check_runs"].append(extra)
        checks["total_count"] += 1
        proof["suite_pages"][0]["check_suites"].append(dict(suite, id=999, conclusion=extra["conclusion"]))
        proof["suite_pages"][0]["total_count"] += 1
    with pytest.raises(ValueError):
        validate_pr_rollup(NUMBER, pr, selected, proof, JOBS)


@pytest.mark.parametrize("status,conclusion", [("completed", "failure"), ("in_progress", None)])
def test_validator_reselects_newest_failed_or_pending_event_on_page_two(tmp_path, status, conclusion):
    pr, selected, proof = event_case(tmp_path)
    runs = proof["run_pages"][0]["workflow_runs"]
    template = proof["workflows"]["Foundation CI"]["run"]
    filler = [dict(template, id=50000 + i, check_suite_id=60000 + i, name=f"Other {i}")
              for i in range(100 - len(runs))]
    newer = dict(template, id=90000, check_suite_id=90001, run_number=4,
                 status=status, conclusion=conclusion)
    proof["run_pages"] = [{"total_count": 101, "workflow_runs": runs + filler},
                          {"total_count": 101, "workflow_runs": [newer]}]
    with pytest.raises(ValueError, match="latest required workflow"):
        validate_pr_rollup(NUMBER, pr, selected, proof, JOBS)


@pytest.mark.parametrize("mode", ["open-detached", "merged-other-pr", "merged-other-branch"])
def test_detached_history_cannot_broaden_existing_pr_boundary(tmp_path, mode):
    data = multiple_event_data(merged=mode != "open-detached", detached=True)
    old = data[f"repos/{REPO}/actions/runs/2011"]
    if mode == "merged-other-pr": old["pull_requests"] = [{"number": NUMBER + 1}]
    if mode == "merged-other-branch": old["head_branch"] = "other"
    client, _ = make_client(tmp_path, data=data)
    with pytest.raises(ValueError):
        proof = collect(client, NUMBER)
        selected = latest_required_runs(_workflow_pages(proof["run_pages"]), HEAD, NUMBER,
            allow_detached=proof["pr"]["state"] == "MERGED", expected_branch=proof["pr"]["headRefName"])
        validate_pr_rollup(NUMBER, proof["pr"], selected, proof, JOBS)


def test_missing_historical_run_metadata_has_no_success_fallback(tmp_path):
    def mutate(response, request):
        if request["params"].get("endpoint") == f"repos/{REPO}/actions/runs/2011":
            response["payload"] = {"message": "Forbidden"}
        return response
    client, _ = make_client(tmp_path, data=multiple_event_data(), mutate=mutate)
    with pytest.raises(ValueError, match="REST returned an error"):
        collect(client, NUMBER)
