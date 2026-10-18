"""Synthetic GitHub peer and isolated Git fixtures; never live evidence input."""
from __future__ import annotations

from copy import deepcopy
import json
import subprocess
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from github_connector_bridge import LiveBridge, PREFIX, TOOLS
import project_state as state
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


def source_waiver_comment(source):
    return {"id": 77, "user": {"login": "owner"}, "author_association": "OWNER",
            "created_at": "2026-10-01T11:45:00Z", "updated_at": "2026-10-01T11:45:00Z",
            "body": (f"Owner waiver for source checkpoint PR #{NUMBER}: APPROVE\n"
                     f"Source HEAD: {source}\nIndependent review: unavailable\n"
                     "Reason: Synthetic owner acceptance fixture\n"
                     "Foundation CI: 11 SUCCESS\nDependency Security: 12 SUCCESS\n"
                     "Review Source: 13 SUCCESS")}


STATE_NAMES = ("PLAN.json", "PACKAGES.json", "CURRENT.md", "CHECKPOINTS.json")


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.PIPE).strip()


def checkout(root, *, decided=True):
    root.mkdir()
    git(root, "init", "--quiet", "--initial-branch", "source")
    git(root, "config", "user.name", "Transport test")
    git(root, "config", "user.email", "transport@example.invalid")
    git(root, "commit", "--quiet", "--allow-empty", "-m", "Fixture base")
    base = git(root, "rev-parse", "HEAD")
    plan = state.load_plan(Path(__file__).resolve().parents[1])
    active = plan["active_package"]
    plan["packages"][active]["status"] = "active"
    plan["packages"][active]["decides_next"] = True
    plan["canonical_lineage"]["working_branch"] = "source"
    plan["canonical_lineage"]["current_package_base"]["sha"] = base
    if not decided:
        plan["packages"]["TEST-TRANSPORT-NEXT"] = {"status": "planned_next", "depends_on": [active], "decides_next": True}
        plan["next_package"] = "TEST-TRANSPORT-NEXT"
    (root / "docs").mkdir()
    state.write_state(plan, {"schema_version": 1, "checkpoints": {}}, root=root)
    scopes = root / "tools/scopes"
    scopes.mkdir(parents=True)
    (scopes / f"{active.lower()}.json").write_text(json.dumps(
        {"package_id": active, "risk": "high", "independent_review_required": True}))
    (root / "marker.txt").write_text("original")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "Fixture source")
    git(root, "branch", "other")
    git(root, "remote", "add", "origin", f"https://github.com/{REPO}.git")
    return plan, git(root, "rev-parse", "HEAD")


def state_bytes(root):
    return {name: (root / "docs" / name).read_bytes() for name in STATE_NAMES}
