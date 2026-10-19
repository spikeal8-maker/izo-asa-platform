"""Workflow-event identity and positively proved historical check supersession."""
from __future__ import annotations

from project_state_rest_checks import WORKFLOW_PATHS, _rows

RUN_KEYS = ("id", "name", "path", "workflow_id", "check_suite_id", "head_sha", "head_branch",
            "event", "status", "conclusion", "run_attempt", "run_number", "updated_at")
TERMINAL = {"success", "failure", "cancelled", "timed_out", "action_required", "skipped",
            "neutral", "stale"}


def _pr_linked(raw: dict, pr: dict) -> bool:
    pulls = raw.get("pull_requests")
    return (isinstance(pulls, list)
            and all(isinstance(row, dict) and type(row.get("number")) is int for row in pulls)
            and (sum(row.get("number") == pr["number"] for row in pulls) == 1
                 or (pulls == [] and pr.get("state") == "MERGED")))


def _workflow_matches(name: str, raw: dict, listed: dict, pr: dict, repo: str) -> bool:
    return (all(raw.get(key) == listed.get(key) for key in RUN_KEYS)
            and all(type(raw.get(key)) is int and raw[key] > 0 and type(listed.get(key)) is int
                    for key in ("id", "workflow_id", "check_suite_id", "run_attempt", "run_number"))
            and raw.get("name") == name and raw.get("path") == WORKFLOW_PATHS.get(name)
            and (raw.get("repository") or {}).get("full_name") == repo
            and (listed.get("repository") or {}).get("full_name") == repo
            and raw.get("head_sha") == pr["headRefOid"] and raw.get("head_branch") == pr["headRefName"]
            and raw.get("event") == "pull_request" and raw.get("status") == "completed"
            and _pr_linked(raw, pr) and _pr_linked(listed, pr))


def _job_checks(run: dict, rows: list, checks: dict, suites: dict, pr: dict, repo: str,
                *, historical: bool = False) -> dict[str, dict]:
    suite = suites.get(run["check_suite_id"]) or {}
    conclusions = TERMINAL if historical else {"success"}
    if (run.get("conclusion") not in conclusions or not isinstance(rows, list) or not rows
            or suite.get("status") != "completed" or suite.get("conclusion") != run["conclusion"]):
        raise ValueError("REST workflow result or suite invalid")
    matched, ids = {}, set()
    for job in rows:
        if not isinstance(job, dict):
            raise ValueError("REST workflow job invalid")
        name, job_id = job.get("name"), job.get("id")
        check = checks.get(job_id, {}) if type(job_id) is int else {}
        url = f"https://github.com/{repo}/actions/runs/{run['id']}/job/{job_id}"
        if (any(type(job.get(key)) is not int or job[key] < 1 for key in ("id", "run_id", "run_attempt"))
                or not isinstance(name, str) or not name or name in matched or job_id in ids
                or job["run_id"] != run["id"] or job["run_attempt"] != run["run_attempt"]
                or job.get("head_sha") != pr["headRefOid"] or job.get("status") != "completed"
                or job.get("conclusion") not in conclusions
                or job.get("run_url") != f"https://api.github.com/repos/{repo}/actions/runs/{run['id']}"
                or job.get("check_run_url") != f"https://api.github.com/repos/{repo}/check-runs/{job_id}"
                or check.get("name") != name or check.get("conclusion") != job["conclusion"]
                or (check.get("check_suite") or {}).get("id") != run["check_suite_id"]
                or ((historical or "details_url" in check) and check.get("details_url") != url)
                or ((historical or "pull_requests" in check) and not _pr_linked(check, pr))):
            raise ValueError("REST job/check belongs to another run/attempt or lacks provenance")
        matched[name] = check
        ids.add(job_id)
    observed = {row["id"] for row in checks.values()
                if (row.get("check_suite") or {}).get("id") == run["check_suite_id"]}
    if observed != ids:
        raise ValueError("REST workflow jobs/checks incomplete or ambiguous")
    return matched


def validate_events(number: int, pr: dict, selected: dict[str, dict], proof: dict,
                    required_jobs: dict[str, set[str]], checks: list[dict],
                    suite_ids: dict, required: dict) -> set[int]:
    from project_state_evidence import _workflow_pages, latest_required_runs
    repo = proof["repository"]
    runs = _rows(proof.get("run_pages"), "workflow_runs")
    run_ids = {row["id"]: row for row in runs}
    if (any(row.get("head_sha") != pr["headRefOid"] or row.get("event") != "pull_request"
            or any(type(row.get(key)) is not int or row[key] < 1
                   for key in ("id", "check_suite_id", "run_number", "run_attempt")) for row in runs)
            or len({row.get("check_suite_id") for row in runs}) != len(runs)):
        raise ValueError("REST workflow history source/event/suite ambiguous")
    latest = latest_required_runs(_workflow_pages(proof["run_pages"]), pr["headRefOid"], number,
        allow_detached=pr["state"] == "MERGED", expected_branch=pr["headRefName"])
    if latest != selected:
        raise ValueError("REST selected workflows differ from complete current event history")
    eligible = [(row.get("name"), row.get("run_number")) for row in runs
                if row.get("name") in required_jobs and row.get("head_branch") == pr["headRefName"]
                and _pr_linked(row, pr)]
    if len(eligible) != len(set(eligible)):
        raise ValueError("REST workflow history has ambiguous event numbers")
    by_id = {row["id"]: row for row in checks}
    current = {}
    for name, jobs in required_jobs.items():
        bundle = (proof.get("workflows") or {}).get(name) or {}
        run, rows = bundle.get("run") or {}, bundle.get("jobs")
        if (run.get("id") != selected[name]["databaseId"]
                or not _workflow_matches(name, run, run_ids.get(run.get("id"), {}), pr, repo)):
            raise ValueError("REST selected workflow identity/attempt differs from required run")
        matched = _job_checks(run, rows, by_id, suite_ids, pr, repo)
        if not jobs <= matched.keys():
            raise ValueError("REST selected workflow has missing required jobs")
        if any((matched[job].get("app") or {}).get("id") != required.get(job) for job in jobs):
            raise ValueError("REST required job/check-run/suite identity mismatch")
        current[name] = matched
    historical = proof.get("historical_workflows")
    if not isinstance(historical, list):
        raise ValueError("REST historical workflow provenance missing")
    seen_runs, historical_ids = {row["databaseId"] for row in selected.values()}, set()
    for bundle in historical:
        run = bundle.get("run") or {}
        name = run.get("name")
        active = (proof.get("workflows", {}).get(name) or {}).get("run") or {}
        if (name not in current or run.get("id") in seen_runs
                or not _workflow_matches(name, run, run_ids.get(run.get("id"), {}), pr, repo)
                or run["workflow_id"] != active["workflow_id"] or run["run_number"] >= active["run_number"]):
            raise ValueError("REST historical workflow lacks strict same-workflow event supersession")
        rows = _rows(bundle.get("job_pages"), "jobs")
        matched = _job_checks(run, rows, by_id, suite_ids, pr, repo, historical=True)
        for job, check in matched.items():
            replacement = current[name].get(job) or {}
            if not replacement or check["app"]["id"] != replacement["app"]["id"]:
                raise ValueError("REST historical check lacks same-context/app successful successor")
            historical_ids.add(check["id"])
        seen_runs.add(run["id"])
    return historical_ids
