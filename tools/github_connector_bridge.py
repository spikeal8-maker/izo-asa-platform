"""Bounded live JSONL channel to a trusted controller using GitHub Connector.

Correlation is not a GitHub signature: the operator must trust the controller.
No file importer or cached-response fallback is provided.
"""
from __future__ import annotations

import hashlib
import json
from queue import Empty, Queue
import re
import secrets
import sys
from threading import Thread
import time
from urllib.parse import parse_qsl, urlsplit

PROTOCOL = "izo-github-connector-v1"
PREFIX = "IZO_GITHUB_REQUEST "
MAX_BYTES = 16 * 1024 * 1024
TTL_SECONDS = 180
MAX_PAGES = 20
TOOLS = {"rest_get": "github_fetch", "job_log": "github_fetch_workflow_job_logs",
         "current_user": "github_get_user_login"}
SHA = r"[0-9a-f]{40}"
ROUTES = (
    r"pulls/[1-9][0-9]*(?:/reviews)?", r"issues/[1-9][0-9]*/comments",
    r"issues/comments/[1-9][0-9]*", rf"commits/{SHA}(?:/check-runs|/check-suites|/status)?",
    rf"compare/{SHA}\.\.\.{SHA}", r"branches/main", r"rulesets",
    r"actions/runs(?:/[1-9][0-9]*(?:/jobs)?)?",
)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_request(repo: str, operation: str, params: dict) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*", repo):
        raise ValueError("Connector repository invalid")
    if operation == "current_user" and params == {}:
        return
    if operation == "job_log" and set(params) == {"job_id"}:
        if type(params["job_id"]) is int and params["job_id"] > 0:
            return
    if operation == "rest_get" and set(params) == {"endpoint"}:
        endpoint = params["endpoint"]
        if not isinstance(endpoint, str):
            raise ValueError("Connector endpoint invalid")
        parsed = urlsplit(endpoint)
        prefix = f"repos/{repo}/"
        query = parse_qsl(parsed.query, keep_blank_values=True)
        allowed_query = {"page", "per_page", "event", "head_sha", "includes_parents", "filter"}
        if (not parsed.scheme and not parsed.netloc and not parsed.fragment
                and parsed.path.startswith(prefix)
                and any(re.fullmatch(pattern, parsed.path[len(prefix):]) for pattern in ROUTES)
                and len(dict(query)) == len(query) and set(dict(query)) <= allowed_query):
            for key, value in query:
                valid = ((key == "page" and value.isdigit() and 1 <= int(value) <= MAX_PAGES)
                         or (key == "per_page" and value == "100")
                         or (key == "event" and value in {"pull_request", "push"})
                         or (key == "head_sha" and re.fullmatch(SHA, value))
                         or (key == "includes_parents" and value == "true")
                         or (key == "filter" and value == "latest"))
                if not valid:
                    raise ValueError("Connector query value is not supported")
            return
    raise ValueError("Connector operation or endpoint is not supported")


def _read_line(stream, timeout: float) -> str:
    queue = Queue(maxsize=1)
    def read():
        try:
            queue.put(stream.readline(MAX_BYTES + 1))
        except Exception as exc:
            queue.put(exc)
    Thread(target=read, daemon=True).start()
    try:
        result = queue.get(timeout=timeout)
    except Empty as exc:
        raise ValueError("Connector response timed out") from exc
    if isinstance(result, Exception):
        raise ValueError("Connector response could not be read") from result
    if not result or not result.endswith("\n") or len(result.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Connector response missing, truncated or too large")
    return result


class LiveBridge:
    def __init__(self, repo: str, *, reader=None, writer=None, clock=time.monotonic):
        self.repo = repo
        self.reader = reader if reader is not None else sys.stdin
        self.writer = writer if writer is not None else sys.stdout
        self.clock = clock
        self.observed: dict[str, tuple[str, dict, str]] = {}
        self.failed = False

    def request(self, operation: str, params: dict, *, mutable: bool = True):
        if self.failed:
            raise ValueError("Connector session already failed")
        validate_request(self.repo, operation, params)
        request = {"protocol": PROTOCOL, "repository": self.repo, "operation": operation,
                   "params": params, "request_id": secrets.token_hex(16),
                   "nonce": secrets.token_hex(32), "ttl_seconds": TTL_SECONDS}
        request["request_digest"] = digest(request)
        started = self.clock()
        self.writer.write(PREFIX + json.dumps(request, ensure_ascii=True) + "\n")
        self.writer.flush()
        try:
            response = json.loads(_read_line(self.reader, TTL_SECONDS))
            identity = {key: request[key] for key in (
                "protocol", "repository", "operation", "request_id", "nonce", "request_digest")}
            if (not isinstance(response, dict) or any(response.get(k) != v for k, v in identity.items())
                    or response.get("ok") is not True or "payload" not in response
                    or response.get("tool") != TOOLS[operation]
                    or self.clock() - started >= TTL_SECONDS):
                raise ValueError("Connector response identity, receipt, freshness or result invalid")
            payload = response["payload"]
            # Explicit error envelopes must never become an empty successful evidence set.
            if isinstance(payload, dict) and (payload.get("isError") or "error" in payload):
                raise ValueError("Connector returned an error payload")
            key = digest([operation, params])
            value = digest(payload)
            if mutable:
                previous = self.observed.get(key)
                if previous and previous[2] != value:
                    raise ValueError("GitHub evidence changed during collection; start a new invocation")
                self.observed[key] = (operation, params.copy(), value)
            return payload
        except (ValueError, TypeError, UnicodeError) as exc:
            self.failed = True
            raise ValueError(f"live Connector evidence rejected: {exc}") from exc

    def revalidate(self) -> None:
        for operation, params, expected in list(self.observed.values()):
            if digest(self.request(operation, params, mutable=False)) != expected:
                self.failed = True
                raise ValueError("GitHub evidence changed before state mutation")
