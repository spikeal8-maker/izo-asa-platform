"""Explicit Connector transport and complete REST pagination for project state."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

from github_connector_bridge import LiveBridge, MAX_PAGES

_ACTIVE: ContextVar[ConnectorClient | None] = ContextVar("project_state_connector", default=None)


def current(root: Path):
    client = _ACTIVE.get()
    if client is not None and root.resolve() != client.root:
        raise ValueError("GitHub transport cannot mix repository roots")
    return client


def before_write(source_head: str, branch: str, evidence: dict, root: Path, *, git_fn) -> None:
    from project_state_workflow import assert_checkout_unchanged
    client = current(root)
    if client is not None:
        client.finish()
        from project_state_evidence import repo_slug
        if repo_slug(root) != client.repo:
            raise ValueError("GitHub origin changed before state mutation")
        merged = evidence.get("merged_source_commit")
        if evidence.get("type") == "completed_merged_closeout":
            merged = evidence["source_head"]
        if merged:
            ref, expected = "refs/heads/main", merged
        elif evidence.get("type") == "pr_merge_tree":
            ref, expected = f"refs/pull/{evidence['verified_pr']}/merge", evidence["tested_merge_tree"]
        else:
            ref = None
        if ref and git_fn("ls-remote", "origin", ref, root=root).split() != [expected, ref]:
            raise ValueError("canonical main or tested PR merge ref changed before state mutation")
    assert_checkout_unchanged(source_head, branch, root=root, git_fn=git_fn)


def add_transport_arguments(parser, root: Path) -> None:
    parser.add_argument("--repo-root", type=Path, default=root,
                        help="exact target checkout; all state and Git operations use this root")
    parser.add_argument("--github-transport", choices=("gh", "connector-stdio"), default="gh",
                        help="explicit live GitHub evidence transport (default: gh)")


@contextmanager
def transport(name: str, root: Path):
    if name not in {"gh", "connector-stdio"}:
        raise ValueError("unknown GitHub transport")
    from project_state_evidence import git, repo_slug
    root = root.resolve()
    if Path(git("rev-parse", "--show-toplevel", root=root)).resolve() != root:
        raise ValueError("--repo-root must be the exact checkout root")
    client = ConnectorClient(root, LiveBridge(repo_slug(root))) if name == "connector-stdio" else None
    token = _ACTIVE.set(client)
    try:
        yield client
    finally:
        _ACTIVE.reset(token)


def workflow_pages(value) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("workflow run response must be paginated")
    pages = value if value and all(isinstance(page, dict) for page in value) else [value]
    result = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        for item in page.get("workflow_runs", []):
            if isinstance(item, dict):
                result.append({
                    "databaseId": item.get("id"), "name": item.get("name"),
                    "status": item.get("status"), "conclusion": item.get("conclusion"),
                    "headSha": item.get("head_sha"), "event": item.get("event"),
                    "headBranch": item.get("head_branch"),
                    "updatedAt": item.get("updated_at"),
                    "runAttempt": item.get("run_attempt"), "runNumber": item.get("run_number"),
                    "prNumbers": [p.get("number") for p in item.get("pull_requests", [])
                                  if isinstance(p, dict) and p.get("number") is not None]})
    return result


class ConnectorClient:
    def __init__(self, root: Path, bridge: LiveBridge):
        self.root, self.bridge, self.repo = root.resolve(), bridge, bridge.repo
        self.runs: dict[int, dict] = {}

    def get(self, endpoint: str, *, paginate: bool = False):
        immutable = re.fullmatch(rf"repos/{re.escape(self.repo)}/commits/[0-9a-f]{{40}}", endpoint)
        if not paginate:
            result = self.bridge.request("rest_get", {"endpoint": endpoint}, mutable=not immutable)
            if not isinstance(result, dict):
                raise ValueError("GitHub REST object missing")
            if result.get("message") or result.get("errors"):
                raise ValueError("GitHub REST returned an error object")
            if immutable and result.get("sha") != endpoint.rsplit("/", 1)[1]:
                raise ValueError("GitHub immutable commit SHA differs from requested SHA")
            return result
        parsed = urlsplit(endpoint)
        query = dict(parse_qsl(parsed.query))
        if "page" in query:
            raise ValueError("pagination must begin with the first page")
        query["per_page"] = "100"
        collection = ("jobs" if parsed.path.endswith("/jobs") else
                      "workflow_runs" if parsed.path.endswith("/actions/runs") else
                      "check_runs" if parsed.path.endswith("/check-runs") else
                      "check_suites" if parsed.path.endswith("/check-suites") else
                      "statuses" if parsed.path.endswith("/status") else None)
        pages, ids, total = [], set(), None
        for number in range(1, MAX_PAGES + 1):
            query["page"] = str(number)
            path = parsed.path + "?" + urlencode(query)
            page = self.bridge.request("rest_get", {"endpoint": path})
            if isinstance(page, list):
                rows = page
                if collection is not None:
                    raise ValueError("GitHub pagination changed response shape")
            elif isinstance(page, dict):
                count = page.get("total_count")
                if (collection not in page or type(count) is not int or not 0 <= count < 1000
                        or (total is not None and total != count)):
                    raise ValueError("GitHub pagination count or collection missing/changed")
                total, rows = count, page[collection]
            else:
                raise ValueError("GitHub paginated response missing")
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError("GitHub pagination collection malformed")
            for item in rows:
                if not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] in ids:
                    raise ValueError("GitHub pagination contains malformed or repeated identity")
                ids.add(item["id"])
                if collection == "workflow_runs":
                    self.runs[item["id"]] = item
            pages.append(page)
            if total is not None:
                if len(ids) > total or (len(rows) < 100 and len(ids) != total):
                    raise ValueError("GitHub pagination is incomplete")
                if len(ids) == total:
                    return pages
            elif len(rows) < 100:
                return pages
        raise ValueError("GitHub pagination exceeds the bounded complete evidence contract")

    def pr(self, number: int) -> dict:
        raw = self.get(f"repos/{self.repo}/pulls/{number}")
        head, base = raw.get("head") or {}, raw.get("base") or {}
        if (not isinstance(head, dict) or not isinstance(base, dict)
                or raw.get("number") != number or (base.get("repo") or {}).get("full_name") != self.repo
                or (head.get("repo") or {}).get("full_name") != self.repo
                or base.get("ref") != "main" or type(raw.get("draft")) is not bool
                or not isinstance(head.get("ref"), str) or not head["ref"]
                or any(not isinstance(row.get("sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", row["sha"])
                       for row in (head, base))
                or raw.get("state") not in {"open", "closed"}
                or type(raw.get("merged")) is not bool or raw["merged"] != bool(raw.get("merged_at"))
                or (raw["merged"] and raw["state"] != "closed")
                or raw.get("html_url") != f"https://github.com/{self.repo}/pull/{number}"):
            raise ValueError("Connector PR number/repository/base identity invalid")
        return {"number": number, "headRefOid": head.get("sha"), "headRefName": head.get("ref"),
                "baseRefOid": base.get("sha"), "baseRefName": base.get("ref"),
                "isDraft": raw["draft"], "state": "MERGED" if raw.get("merged_at") else
                str(raw.get("state", "")).upper(), "url": raw.get("html_url"),
                "createdAt": raw.get("created_at"), "mergedAt": raw.get("merged_at"),
                "mergeCommit": {"oid": raw.get("merge_commit_sha")}}

    def actor(self) -> dict:
        raw = self.bridge.request("current_user", {})
        # The controller forwards the purpose-built get_user_login result unchanged.
        if not isinstance(raw, dict) or not isinstance(raw.get("login"), str) or not raw["login"]:
            raise ValueError("Connector authenticated login missing")
        return raw

    def workflow_jobs(self, run_id: int) -> tuple[dict, list[dict]]:
        run = self.get(f"repos/{self.repo}/actions/runs/{run_id}")
        selected = self.runs.get(run_id)
        keys = ("id", "name", "path", "head_sha", "head_branch", "event", "status", "conclusion",
                "check_suite_id", "workflow_id", "run_attempt", "run_number", "updated_at")
        if (run.get("id") != run_id or (run.get("repository") or {}).get("full_name") != self.repo
                or selected is None or any(run.get(key) != selected.get(key) for key in keys)
                or type(run.get("run_attempt")) is not int or run["run_attempt"] < 1
                or run.get("status") != "completed" or run.get("conclusion") != "success"):
            raise ValueError("Connector workflow run identity/attempt/result invalid")
        pages = self.get(f"repos/{self.repo}/actions/runs/{run_id}/jobs?filter=latest", paginate=True)
        jobs = [row for page in pages for row in page["jobs"]]
        if not jobs:
            raise ValueError("Connector workflow jobs missing")
        for job in jobs:
            if (job.get("run_id") != run_id or job.get("run_attempt") != run["run_attempt"]
                    or job.get("head_sha") != run.get("head_sha")
                    or job.get("status") != "completed" or job.get("conclusion") != "success"
                    or job.get("run_url") != f"https://api.github.com/repos/{self.repo}/actions/runs/{run_id}"
                    or job.get("check_run_url") != f"https://api.github.com/repos/{self.repo}/check-runs/{job['id']}"):
                raise ValueError("Connector job does not belong to the selected run/attempt")
        return run, jobs

    def workflow_log(self, run_id: int) -> str:
        _, jobs = self.workflow_jobs(run_id)
        logs = []
        for job in jobs:
            log = self.bridge.request("job_log", {"job_id": job["id"]}, mutable=False)
            if not isinstance(log, str) or not log.strip():
                raise ValueError("Connector full workflow job log missing")
            logs.append(log)
        return "\n".join(logs)

    def finish(self) -> None:
        self.bridge.revalidate()
