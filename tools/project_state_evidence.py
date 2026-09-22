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
    successful: dict[str, int] = {}
    for name in REQUIRED_WORKFLOWS:
        candidates = [item for item in runs if item.get("name") == name and item.get("headSha") == expected_head]
        passed = [item for item in candidates if item.get("event") == "pull_request" and item.get("conclusion") == "success"]
        if not passed:
            raise ValueError(f"required workflow {name!r} is not successful for source head {expected_head}")
        successful[name] = int(passed[0]["databaseId"])
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
    runs = gh_json(["run", "list", "--repo", slug, "--commit", expected_head,
                    "--event", "pull_request", "--json",
                    "databaseId,name,conclusion,headSha,event", "--limit", "30"], root=root)
    merge_sha = merge_ref_sha(pr_number, root=root)
    merge_commit = gh_json(["api", f"repos/{slug}/commits/{merge_sha}"], root=root)
    foundation = next((item for item in runs
        if item.get("name") == "Foundation CI" and item.get("headSha") == expected_head
        and item.get("event") == "pull_request" and item.get("conclusion") == "success"), None)
    if foundation is None:
        raise ValueError(f"required workflow 'Foundation CI' is not successful for source head {expected_head}")
    tree = foundation_tested_sha(int(foundation["databaseId"]), slug, root=root)
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
    reviews = gh_json(["api", f"repos/{slug}/pulls/{pr_number}/reviews?per_page=100"], root=root)
    actor = gh_json(["api", "user"], root=root).get("login") if owner_waiver else None
    return review_decision(
        scope, reviews, source_sha, owner_login=slug.split("/", 1)[0], actor_login=actor,
        owner_waiver=owner_waiver, independent_review_unavailable=independent_review_unavailable,
        owner_waiver_source=owner_waiver_source, owner_waiver_reason=owner_waiver_reason)
