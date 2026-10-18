"""Synthetic transport data only; never usable as live state evidence input."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from github_connector_bridge import LiveBridge, PREFIX, TOOLS
from project_state_connector import ConnectorClient
from project_state_rest_checks import WORKFLOW_PATHS

REPO, NUMBER = "owner/repo", 7
HEAD, BASE, MERGE, TESTED, TREE = (c * 40 for c in "abcde")
JOBS = {"Foundation CI": {"verify", "bootstrap-windows"},
        "Dependency Security": {"npm-audit"}, "Review Source": {"snapshot"}}


class Broker:
    """In-memory test peer; its synthetic origin is intentional and explicit."""
    def __init__(self, data=None, mutate=None):
        self.data, self.mutate = data or {}, mutate
        self.requests, self.responses = [], []

    def write(self, line):
        assert line.startswith(PREFIX)
        request = json.loads(line[len(PREFIX):])
        self.requests.append(request)
        if request["operation"] == "rest_get":
            parsed = urlsplit(request["params"]["endpoint"])
            raw = deepcopy(self.data[parsed.path])
            page = int(parse_qs(parsed.query).get("page", ["1"])[0])
            if isinstance(raw, list):
                raw = raw[100 * (page - 1):100 * page]
            elif "total_count" in raw:
                key = next(k for k in ("workflow_runs", "jobs", "check_runs", "check_suites", "statuses") if k in raw)
                raw[key] = raw[key][100 * (page - 1):100 * page]
        elif request["operation"] == "job_log":
            raw = deepcopy(self.data[f"log:{request['params']['job_id']}"])
        else:
            raw = {"login": "owner"}
        response = {key: request[key] for key in (
            "protocol", "repository", "operation", "request_id", "nonce", "request_digest")}
        response.update(ok=True, payload=raw, tool=TOOLS[request["operation"]])
        if self.mutate:
            response = self.mutate(response, request)
        self.responses.append(json.dumps(response) + "\n" if isinstance(response, dict) else response)

    def flush(self):
        pass

    def readline(self, _size):
        return self.responses.pop(0)


def data_set() -> dict:
    prefix = f"repos/{REPO}"
    pr = {"number": NUMBER, "draft": False, "state": "closed", "merged": True,
          "html_url": f"https://github.com/{REPO}/pull/{NUMBER}",
          "head": {"sha": HEAD, "ref": "codex/test-package", "repo": {"full_name": REPO}},
          "base": {"sha": BASE, "ref": "main", "repo": {"full_name": REPO}},
          "created_at": "2026-10-01T11:00:00Z", "merged_at": "2026-10-01T12:00:00Z",
          "merge_commit_sha": MERGE}
    checks, suites, runs = [], [], []
    data = {f"{prefix}/pulls/{NUMBER}": pr, f"{prefix}/rulesets": [],
            f"{prefix}/pulls/{NUMBER}/reviews": [], f"{prefix}/issues/{NUMBER}/comments": []}
    for i, (name, names) in enumerate(JOBS.items(), 11):
        run = {"id": i, "name": name, "path": WORKFLOW_PATHS[name], "event": "pull_request",
               "head_sha": HEAD, "head_branch": pr["head"]["ref"], "check_suite_id": i + 100,
               "run_attempt": 1, "run_number": 3, "workflow_id": i + 200,
               "status": "completed", "conclusion": "success", "pull_requests": [{"number": NUMBER}],
               "repository": {"full_name": REPO}, "updated_at": "2026-10-01T11:30:00Z"}
        runs.append(run)
        suites.append({"id": run["check_suite_id"], "head_sha": HEAD, "app": {"id": 42},
                       "status": "completed", "conclusion": "success"})
        data[f"{prefix}/actions/runs/{i}"] = run
        jobs = []
        for n, job_name in enumerate(sorted(names), 1):
            job_id = i * 10 + n
            jobs.append({"id": job_id, "name": job_name, "run_id": i, "run_attempt": 1, "head_sha": HEAD,
                         "status": "completed", "conclusion": "success",
                         "run_url": f"https://api.github.com/{prefix}/actions/runs/{i}",
                         "check_run_url": f"https://api.github.com/{prefix}/check-runs/{job_id}"})
            checks.append({"id": job_id, "name": job_name, "head_sha": HEAD, "status": "completed",
                           "conclusion": "success", "app": {"id": 42}, "check_suite": {"id": i + 100}})
            data[f"log:{job_id}"] = f"Full synthetic log\nIZO_BUILD_SHA: {TESTED}\nFinished\n"
        data[f"{prefix}/actions/runs/{i}/jobs"] = {"total_count": len(jobs), "jobs": jobs}
    data[f"{prefix}/actions/runs"] = {"total_count": len(runs), "workflow_runs": runs}
    data[f"{prefix}/commits/{HEAD}/check-runs"] = {"total_count": len(checks), "check_runs": checks}
    data[f"{prefix}/commits/{HEAD}/check-suites"] = {"total_count": len(suites), "check_suites": suites}
    data[f"{prefix}/commits/{HEAD}/status"] = {"total_count": 0, "statuses": [], "state": "pending",
                                             "sha": HEAD, "repository": {"full_name": REPO}}
    contexts = sorted({job for names in JOBS.values() for job in names})
    data[f"{prefix}/branches/main"] = {"name": "main", "protected": True, "commit": {"sha": MERGE},
        "protection": {"enabled": True, "required_status_checks": {"enforcement_level": "everyone",
        "contexts": contexts, "checks": [{"context": name, "app_id": 42} for name in contexts]}}}
    for sha in (MERGE, TESTED):
        data[f"{prefix}/commits/{sha}"] = {"sha": sha, "parents": [{"sha": BASE}, {"sha": HEAD}],
                                          "commit": {"tree": {"sha": TREE}}}
    return data


def make_client(root=Path("."), *, data=None, mutate=None):
    broker = Broker(data if data is not None else data_set(), mutate)
    return ConnectorClient(root, LiveBridge(REPO, reader=broker, writer=broker)), broker
