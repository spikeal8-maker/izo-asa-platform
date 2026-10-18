"""Live bridge correlation, bounded protocol and response freshness failures."""
from __future__ import annotations

import json

import pytest

from state_transport_fixtures import Broker, REPO, make_client
from github_connector_bridge import LiveBridge, TTL_SECONDS, digest, validate_request


@pytest.mark.parametrize("field", ["protocol", "repository", "operation", "request_id", "nonce",
                                    "request_digest", "tool", "ok", "payload"])
def test_missing_response_field_fails_closed(field):
    def mutate(response, _):
        response.pop(field)
        return response
    client, _ = make_client(mutate=mutate)
    with pytest.raises(ValueError, match="rejected"):
        client.actor()
    with pytest.raises(ValueError, match="already failed"):
        client.actor()


@pytest.mark.parametrize("mode", ["eof", "truncated", "invalid-json", "wrong-id", "wrong-repo",
                                   "wrong-tool", "api-error", "expired", "replay"])
def test_protocol_rejects_unusable_or_replayed_live_receipt(mode):
    old = []
    def mutate(response, _):
        if mode == "eof": return ""
        if mode == "truncated": return json.dumps(response)
        if mode == "invalid-json": return "not-json\n"
        if mode == "wrong-id": response["request_id"] = "wrong"
        if mode == "wrong-repo": response["repository"] = "another/repo"
        if mode == "wrong-tool": response["tool"] = "read_file"
        if mode == "api-error": response["payload"] = {"isError": True}
        if mode == "replay":
            if old: return old[0]
            old.append(response)
        return response
    client, _ = make_client(mutate=mutate)
    if mode == "expired":
        ticks = iter([0, TTL_SECONDS + 1])
        client.bridge.clock = lambda: next(ticks)
    if mode == "replay": client.actor()
    with pytest.raises(ValueError, match="rejected"):
        client.actor()


def test_each_request_is_fresh_and_final_collection_is_revalidated():
    client, broker = make_client()
    assert client.actor() == {"login": "owner"}
    client.finish()
    first, second = broker.requests
    assert first["nonce"] != second["nonce"]
    assert first["request_id"] != second["request_id"]
    assert first["request_digest"] == digest({k: v for k, v in first.items() if k != "request_digest"})


def test_changed_evidence_fails_the_final_barrier():
    client, broker = make_client()
    client.actor()
    broker.mutate = lambda response, _: dict(response, payload={"login": "other"})
    with pytest.raises(ValueError, match="changed before"):
        client.finish()


@pytest.mark.parametrize("op,params", [
    ("rest_post", {}), ("current_user", {"token": "none"}), ("job_log", {"job_id": -1}),
    ("rest_get", {"endpoint": "https://evil.test/repos/owner/repo/pulls/7"}),
    ("rest_get", {"endpoint": "repos/another/repo/pulls/7"}),
    ("rest_get", {"endpoint": "repos/owner/repo/secrets"}),
    ("rest_get", {"endpoint": "repos/owner/repo/pulls/7?state=closed"}),
    ("rest_get", {"endpoint": "repos/owner/repo/pulls/7?page=999"}),
    ("rest_get", {"endpoint": "repos/owner/repo/pulls/7?page=1&page=2"}),
])
def test_unknown_operations_and_endpoints_are_never_issued(op, params):
    broker = Broker()
    with pytest.raises(ValueError):
        LiveBridge(REPO, reader=broker, writer=broker).request(op, params)
    assert broker.requests == []


def test_error_object_cannot_masquerade_as_empty_pages():
    client, _ = make_client(mutate=lambda response, _: dict(response, payload={"message": "Forbidden"}))
    with pytest.raises(ValueError, match="pagination"):
        client.get("repos/owner/repo/rulesets?includes_parents=true", paginate=True)


def test_supported_reads_stay_repo_scoped():
    validate_request(REPO, "job_log", {"job_id": 9})
    validate_request(REPO, "rest_get", {"endpoint": "repos/owner/repo/rulesets?includes_parents=true&page=1&per_page=100"})
