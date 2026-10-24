"""The wrong vendor's key must never overwrite another provider credential."""
from uuid import uuid4

import pytest

from izo.chat.provider_key_validation import key_belongs_to_other_provider
from test_chat_http import http_env, signup, save_and_verify


@pytest.mark.parametrize(("provider", "wrong_key"), [
    ("deepseek", "sk-or-v1-" + "a" * 64),
    ("openrouter", "sk-" + "b" * 32),
])
def test_cross_provider_credential_is_rejected_before_storage(
        http_env, provider, wrong_key):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    response = client.post(
        f"/api/v1/chat/credentials/{provider}",
        json={"operation_id": str(uuid4()), "key": wrong_key},
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "credential_provider_mismatch"}}
    assert wrong_key not in response.text
    listed = client.get("/api/v1/chat/credentials")
    assert listed.status_code == 200
    assert all(not item["configured"]
               for item in listed.json()["credentials"])


def test_invalid_rotation_cannot_replace_an_existing_verified_key(http_env):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    verified = save_and_verify(client)
    rejected = client.post(
        "/api/v1/chat/credentials/deepseek",
        json={
            "operation_id": str(uuid4()),
            "key": "sk-or-v1-" + "c" * 64,
            "expected_revision": verified["revision"],
        },
    )
    assert rejected.status_code == 422
    current = client.get("/api/v1/chat/credentials/deepseek")
    assert current.status_code == 200
    assert current.json()["verified"]
    assert current.json()["revision"] == verified["revision"]
    assert current.json()["generation"] == verified["generation"]


def test_provider_shaped_keys_still_can_be_stored_for_real_verification(http_env):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    for provider, key in (
        ("deepseek", "sk-" + "d" * 32),
        ("openrouter", "sk-or-v1-" + "e" * 64),
    ):
        saved = client.post(
            f"/api/v1/chat/credentials/{provider}",
            json={"operation_id": str(uuid4()), "key": key},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["provider"] == provider
        assert saved.json()["configured"] is True
        assert saved.json()["verified"] is False
        assert key not in saved.text
    final = client.get("/api/v1/chat/credentials")
    assert all(row["configured"] for row in final.json()["credentials"])


@pytest.mark.parametrize(("provider", "key", "mismatch"), [
    ("deepseek", "sk-or-v1-" + "a" * 64, True),
    ("openrouter", "sk-" + "f" * 32, True),
    ("deepseek", "sk-" + "f" * 32, False),
    ("openrouter", "sk-or-v1-" + "a" * 64, False),
    ("deepseek", "x" * 32, False),
    ("openrouter", "or-" + "x" * 32, False),
])
def test_synthetic_and_real_key_prefix_detection(provider, key, mismatch):
    assert key_belongs_to_other_provider(provider, key) is mismatch
