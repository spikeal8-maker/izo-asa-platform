"""REST proof of app-bound required checks, distinct from GraphQL isRequired.

This bounded contract supports classic protected main with no repository/inherited
rulesets. Any ruleset requires a separately reviewed implementation, never inference.
"""
from __future__ import annotations

KIND = "github_rest_required_checks_v1"
WORKFLOW_PATHS = {"Foundation CI": ".github/workflows/ci.yml",
                  "Dependency Security": ".github/workflows/dependency-audit.yml",
                  "Review Source": ".github/workflows/review-source.yml"}


def collect(client, number: int) -> dict:
    from project_state_evidence import _workflow_pages, latest_required_runs
    pr = client.pr(number)
    repo, head = client.repo, pr["headRefOid"]
    run_pages = client.get(f"repos/{repo}/actions/runs?event=pull_request&head_sha={head}", paginate=True)
    selected = latest_required_runs(_workflow_pages(run_pages), head, number,
        allow_detached=pr["state"] == "MERGED", expected_branch=pr["headRefName"])
    workflows = {}
    for name, item in selected.items():
        run, jobs = client.workflow_jobs(item["databaseId"])
        workflows[name] = {"run": run, "jobs": jobs}
    return {"kind": KIND, "repository": repo, "pr": pr,
            "branch": client.get(f"repos/{repo}/branches/main"),
            "rulesets": [row for page in client.get(
                f"repos/{repo}/rulesets?includes_parents=true", paginate=True) for row in page],
            "check_pages": client.get(f"repos/{repo}/commits/{head}/check-runs?filter=latest", paginate=True),
            "suite_pages": client.get(f"repos/{repo}/commits/{head}/check-suites", paginate=True),
            "status_pages": client.get(f"repos/{repo}/commits/{head}/status", paginate=True),
            "workflows": workflows}


def _rows(pages, key: str) -> list[dict]:
    if not isinstance(pages, list) or not pages:
        raise ValueError("REST required-check pagination missing")
    result, total = [], pages[0].get("total_count") if isinstance(pages[0], dict) else None
    # Enumerate suites separately too: check-run count alone cannot prove the API cap is safe.
    if type(total) is not int or not 0 <= total < 1000:
        raise ValueError("REST required-check pagination count unsupported")
    for page in pages:
        if not isinstance(page, dict) or page.get("total_count") != total or not isinstance(page.get(key), list):
            raise ValueError("REST required-check pagination malformed")
        result.extend(page[key])
    if (len(result) != total or any(not isinstance(row, dict) or type(row.get("id")) is not int for row in result)
            or len({row["id"] for row in result}) != total):
        raise ValueError("REST required-check pagination incomplete or duplicate")
    return result


def _protection(proof: dict) -> dict[str, int]:
    branch = proof.get("branch") or {}
    protection = branch.get("protection") or {}
    required = protection.get("required_status_checks") or {}
    if (branch.get("name") != "main" or branch.get("protected") is not True
            or protection.get("enabled") is not True
            or required.get("enforcement_level") != "everyone" or proof.get("rulesets") != []):
        raise ValueError("REST required checks need complete classic main protection without rulesets")
    contexts, checks = required.get("contexts"), required.get("checks")
    if (not isinstance(contexts, list) or not contexts
            or any(not isinstance(name, str) or not name for name in contexts)
            or len(set(contexts)) != len(contexts) or not isinstance(checks, list)):
        raise ValueError("REST required check contexts missing or ambiguous")
    result = {}
    for check in checks:
        if (not isinstance(check, dict) or not isinstance(check.get("context"), str)
                or check["context"] in result or type(check.get("app_id")) is not int or check["app_id"] < 1):
            raise ValueError("REST required checks must have unambiguous real app IDs")
        result[check["context"]] = check["app_id"]
    if set(result) != set(contexts):
        raise ValueError("REST protection contexts/checks are incomplete")
    return result


def _workflow_matches(name: str, raw: dict, selected: dict, pr: dict, repo: str) -> bool:
    return (raw.get("id") == selected.get("databaseId")
            and type(raw.get("id")) is int and raw["id"] > 0
            and raw.get("name") == name and raw.get("path") == WORKFLOW_PATHS.get(name)
            and type(raw.get("workflow_id")) is int and raw["workflow_id"] > 0
            and type(raw.get("check_suite_id")) is int and raw["check_suite_id"] > 0
            and (raw.get("repository") or {}).get("full_name") == repo
            and raw.get("head_sha") == pr["headRefOid"] and raw.get("head_branch") == pr["headRefName"]
            and raw.get("event") == "pull_request" and raw.get("status") == "completed"
            and raw.get("conclusion") == "success"
            and type(raw.get("run_attempt")) is int and raw["run_attempt"] > 0
            and raw["run_attempt"] == selected.get("runAttempt")
            and raw.get("run_number") == selected.get("runNumber")
            and raw.get("updated_at") == selected.get("updatedAt"))


def validate(number: int, pr: dict, selected: dict[str, dict], proof: dict,
             required_jobs: dict[str, set[str]]) -> None:
    identity = proof.get("pr") or {}
    repo = proof.get("repository")
    if (proof.get("kind") != KIND or not isinstance(repo, str) or identity.get("number") != number
            or any(identity.get(key) != pr.get(key) for key in ("headRefOid", "headRefName", "baseRefOid"))
            or identity.get("baseRefName") != "main"):
        raise ValueError("REST required-check PR identity mismatch")
    required = _protection(proof)
    checks = _rows(proof.get("check_pages"), "check_runs")
    suites = _rows(proof.get("suite_pages"), "check_suites")
    suite_ids = {row["id"]: row for row in suites}
    if any(row.get("head_sha") != pr["headRefOid"] for row in suites):
        raise ValueError("REST check suite belongs to another source SHA")
    statuses = _rows(proof.get("status_pages"), "statuses")
    for page in proof["status_pages"]:
        if (page.get("sha") != pr["headRefOid"] or (page.get("repository") or {}).get("full_name") != repo
                or (statuses and page.get("state") != "success")):
            raise ValueError("REST legacy status identity or aggregate failed")
    # Empty legacy channel may have aggregate 'pending'; no context exists to block.
    if any(row.get("state") != "success" or not row.get("context") for row in statuses):
        raise ValueError("REST legacy status contains pending or failed context")
    for row in checks:
        suite = suite_ids.get((row.get("check_suite") or {}).get("id")) or {}
        if (row.get("head_sha") != pr["headRefOid"] or row.get("status") != "completed"
                or row.get("conclusion") != "success" or not row.get("name")
                or not suite or (suite.get("app") or {}).get("id") != (row.get("app") or {}).get("id")):
            raise ValueError("REST check rollup contains foreign, pending or failed check")
    keyed = {}
    for check in checks:
        key = (check["name"], (check.get("app") or {}).get("id"))
        if key in keyed:
            raise ValueError("REST latest checks contain ambiguous name/app identity")
        keyed[key] = check
    if any((name, app) not in keyed for name, app in required.items()):
        raise ValueError("REST required app-bound check missing")
    for name, jobs in required_jobs.items():
        bundle = (proof.get("workflows") or {}).get(name) or {}
        run, rows = bundle.get("run") or {}, bundle.get("jobs")
        if not _workflow_matches(name, run, selected[name], pr, repo) or not isinstance(rows, list):
            raise ValueError("REST selected workflow identity/attempt differs from required run")
        matched = set()
        for job in rows:
            if not isinstance(job, dict):
                raise ValueError("REST workflow job invalid")
            job_name, job_id = job.get("name"), job.get("id")
            if (type(job_id) is not int or job.get("run_id") != run["id"]
                    or job.get("run_attempt") != run["run_attempt"] or job.get("head_sha") != pr["headRefOid"]
                    or job.get("status") != "completed" or job.get("conclusion") != "success"
                    or job.get("check_run_url") != f"https://api.github.com/repos/{repo}/check-runs/{job_id}"):
                raise ValueError("REST job belongs to another workflow run/attempt")
            if job_name in jobs:
                check = keyed.get((job_name, required.get(job_name))) or {}
                if (job_name in matched or check.get("id") != job_id
                        or (check.get("check_suite") or {}).get("id") != run["check_suite_id"]
                        or suite_ids[run["check_suite_id"]].get("status") != "completed"
                        or suite_ids[run["check_suite_id"]].get("conclusion") != "success"):
                    raise ValueError("REST required job/check-run/suite identity mismatch")
                matched.add(job_name)
        if not jobs <= matched:
            raise ValueError("REST selected workflow has missing required jobs")
