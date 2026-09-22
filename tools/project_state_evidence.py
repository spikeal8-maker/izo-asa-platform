"""GitHub/CI evidence collection for project-state transitions."""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse

from project_state_model import ROOT
from review_evidence import review_decision, review_required

REQUIRED_WORKFLOWS = ("Foundation CI", "Dependency Security", "Review Source")


def run(args: list[str], *, root: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="strict", timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"command failed: {' '.join(args)}")
    return result.stdout.strip()


def git(*args: str, root: Path = ROOT) -> str:
    return run(["git", *args], root=root)


def repo_slug(root: Path = ROOT) -> str:
    remote = git("remote", "get-url", "origin", root=root).strip()
    if remote.startswith("git@github.com:"):
        value = remote.split(":", 1)[1]
    else:
        parsed = urlparse(remote)
        if parsed.hostname != "github.com":
            raise ValueError("origin must point to github.com")
        value = parsed.path.lstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if value.count("/") != 1:
        raise ValueError("cannot derive owner/repo from origin")
    return value


def gh_json(args: list[str], *, root: Path = ROOT):
    return json.loads(run(["gh", *args], root=root))


def _flatten_pages(value) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("paginated GitHub response must be a list")
    if value and all(isinstance(page, list) for page in value):
        return [item for page in value for item in page if isinstance(item, dict)]
    return [item for item in value if isinstance(item, dict)]


def _workflow_pages(value) -> list[dict]:
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
                    "runAttempt": item.get("run_attempt"), "runNumber": item.get("run_number"),
                    "prNumbers": [p.get("number") for p in item.get("pull_requests", [])
                                  if isinstance(p, dict) and p.get("number") is not None]})
    return result


def _pr_matches(item: dict, pr_number: int) -> bool:
    numbers = item.get("prNumbers")
    if numbers is None:
        pulls = item.get("pull_requests")
        if pulls is None:
            return True
        numbers = [p.get("number") for p in pulls if isinstance(p, dict)]
    return pr_number in numbers


def _freshness(item: dict) -> tuple[int, int, int]:
    result = []
    for keys in (("runNumber", "run_number"), ("runAttempt", "run_attempt"), ("databaseId", "id")):
        value = 0
        for key in keys:
            try:
                if item.get(key) is not None:
                    value = int(item[key]); break
            except (TypeError, ValueError):
                pass
        result.append(value)
    return tuple(result)


def latest_required_runs(runs: list[dict], expected_head: str, pr_number: int) -> dict[str, dict]:
    selected = {}
    for name in REQUIRED_WORKFLOWS:
        candidates = [item for item in runs if item.get("name") == name
                      and item.get("headSha") == expected_head
                      and item.get("event") == "pull_request" and _pr_matches(item, pr_number)]
        if not candidates:
            raise ValueError(f"required workflow {name!r} has no run for PR #{pr_number} source head {expected_head}")
        latest = max(candidates, key=_freshness)
        status = str(latest.get("status") or "completed").lower()
        conclusion = str(latest.get("conclusion") or "").lower()
        if status != "completed" or conclusion != "success":
            raise ValueError(f"latest required workflow {name!r} for PR #{pr_number} source head "
                             f"{expected_head} is {status}/{conclusion or 'none'}")
        selected[name] = latest
    return selected


def foundation_tested_sha(run_id: int, slug: str, *, root: Path = ROOT) -> str:
    log = run(["gh", "run", "view", str(run_id), "--repo", slug, "--log"], root=root)
    values = set(re.findall(r"IZO_BUILD_SHA:\s*([0-9a-f]{40})", log))
    if len(values) != 1:
        raise ValueError(f"Foundation CI {run_id} does not expose one tested IZO_BUILD_SHA: {sorted(values)}")
    return values.pop()


def merge_ref_sha(pr_number: int, *, root: Path = ROOT) -> str:
    text = git("ls-remote", "origin", f"refs/pull/{pr_number}/merge", root=root)
    sha = text.split()[0] if text else ""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError(f"PR #{pr_number} has no resolvable merge ref")
    return sha


def validate_pr_evidence(*, pr: dict, runs: list[dict], merge_sha: str,
                         merge_commit: dict, expected_head: str, pr_number: int,
                         foundation_tree: str) -> dict:
    if pr.get("headRefOid") != expected_head:
        raise ValueError(f"PR #{pr_number} head {pr.get('headRefOid')} != expected {expected_head}")
    if str(pr.get("state", "")).upper() != "OPEN":
        raise ValueError(f"PR #{pr_number} must still be open while used as checkpoint evidence")
    latest = latest_required_runs(runs, expected_head, pr_number)
    successful = {name: int(latest[name]["databaseId"]) for name in REQUIRED_WORKFLOWS}
    parents = [item.get("sha") for item in merge_commit.get("parents", [])]
    base_head = pr.get("baseRefOid")
    if expected_head not in parents or base_head not in parents:
        raise ValueError(f"PR merge tree {merge_sha} does not contain current source/base parents")
    if not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        raise ValueError("merge tree SHA is invalid")
    if foundation_tree != merge_sha:
        raise ValueError(f"Foundation CI tested merge tree {foundation_tree}, current PR merge tree is {merge_sha}")
    return {"type": "pr_merge_tree", "source_head": expected_head, "verified_pr": pr_number,
            "base_head": base_head, "tested_merge_tree": merge_sha, "workflows": successful}


def fetch_pr_evidence(pr_number: int, expected_head: str, *, root: Path = ROOT) -> dict:
    slug = repo_slug(root)
    pr = gh_json(["pr", "view", str(pr_number), "--repo", slug,
                  "--json", "headRefOid,baseRefOid,isDraft,state,url"], root=root)
    pages = gh_json(["api", "--paginate", "--slurp",
                     f"repos/{slug}/actions/runs?event=pull_request&head_sha={expected_head}&per_page=100"], root=root)
    runs = _workflow_pages(pages)
    latest = latest_required_runs(runs, expected_head, pr_number)
    merge_sha = merge_ref_sha(pr_number, root=root)
    merge_commit = gh_json(["api", f"repos/{slug}/commits/{merge_sha}"], root=root)
    tree = foundation_tested_sha(int(latest["Foundation CI"]["databaseId"]), slug, root=root)
    return validate_pr_evidence(pr=pr, runs=runs, merge_sha=merge_sha, merge_commit=merge_commit,
        expected_head=expected_head, pr_number=pr_number, foundation_tree=tree)


def fetch_review_evidence(scope: dict, pr_number: int, source_sha: str, *,
                          owner_waiver: bool = False,
                          independent_review_unavailable: bool = False,
                          owner_waiver_source: str | None = None,
                          owner_waiver_reason: str | None = None,
                          root: Path = ROOT) -> dict:
    if not review_required(scope):
        return {"independent_review": "not_required", "owner_waiver": False}
    slug = repo_slug(root)
    pages = gh_json(["api", "--paginate", "--slurp",
                     f"repos/{slug}/pulls/{pr_number}/reviews?per_page=100"], root=root)
    reviews = _flatten_pages(pages)
    actor = gh_json(["api", "user"], root=root).get("login") if owner_waiver else None
    return review_decision(
        scope, reviews, source_sha, owner_login=slug.split("/", 1)[0], actor_login=actor,
        owner_waiver=owner_waiver, independent_review_unavailable=independent_review_unavailable,
        owner_waiver_source=owner_waiver_source, owner_waiver_reason=owner_waiver_reason)
