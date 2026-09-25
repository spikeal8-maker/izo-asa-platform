"""Focused credential live-path regressions."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.chat import tables as chat
from izo.chat.credentials import ChatError
from izo.chat.provider import FakeDeepSeekProvider, ProviderFailure
from izo.chat.schemas import (
    CREDENTIAL_WINDOW_LIMIT, CredentialCommand, CredentialWrite,
)
from izo.chat.service import ChatService
from test_chat import KEY, chat_env, connect_key


class FailingVerifyProvider(FakeDeepSeekProvider):
    def __init__(self, code: str):
        self.code = code

    def verify(self, key: str, timeout: int = 15) -> None:
        raise ProviderFailure(self.code)


@pytest.mark.parametrize(("code", "status"), [
    ("provider_unavailable", 503),
    ("credential_rejected", 422),
])
def test_verify_failure_keeps_saved_credential(chat_env, code, status):
    service, alice, _, _ = chat_env
    saved = service.save_credential(
        alice.bearer, alice.view.csrf_token,
        CredentialWrite(operation_id=uuid4(), key=KEY),
    )
    service.provider = FailingVerifyProvider(code)
    with pytest.raises(ChatError, match=code) as failure:
        service.verify_credential(
            alice.bearer, alice.view.csrf_token,
            CredentialCommand(
                operation_id=uuid4(),
                expected_revision=saved.revision,
            ),
        )
    assert failure.value.status == status
    current = service.credential(alice.bearer)
    assert current.configured and current.enabled and not current.verified
    assert current.revision == saved.revision
    assert current.generation == saved.generation


def test_repeated_save_verify_keeps_rate_limit_and_no_half_state(chat_env):
    service, alice, _, _ = chat_env
    verified = None
    for _ in range(3):
        saved = service.save_credential(
            alice.bearer, alice.view.csrf_token,
            CredentialWrite(
                operation_id=uuid4(), key=KEY,
                expected_revision=verified.revision if verified else None,
            ),
        )
        verified = service.verify_credential(
            alice.bearer, alice.view.csrf_token,
            CredentialCommand(
                operation_id=uuid4(),
                expected_revision=saved.revision,
            ),
        )
        assert verified.verified

    with service.engine.begin() as conn:
        count = conn.execute(sa.select(chat.limits.c.count).where(
            chat.limits.c.account_id == alice.view.account.id,
            chat.limits.c.kind == "credential",
        )).scalar_one()
    assert count == CREDENTIAL_WINDOW_LIMIT

    with pytest.raises(ChatError, match="chat_rate_limited"):
        service.save_credential(
            alice.bearer, alice.view.csrf_token,
            CredentialWrite(
                operation_id=uuid4(), key=KEY,
                expected_revision=verified.revision,
            ),
        )
    assert service.credential(alice.bearer) == verified


def test_save_reserves_verify_headroom_before_mutating(chat_env):
    service, alice, _, _ = chat_env
    verified = connect_key(service, alice)
    with service.engine.begin() as conn:
        conn.execute(sa.update(chat.limits).where(
            chat.limits.c.account_id == alice.view.account.id,
            chat.limits.c.kind == "credential",
        ).values(count=CREDENTIAL_WINDOW_LIMIT - 1))

    with pytest.raises(ChatError, match="chat_rate_limited"):
        service.save_credential(
            alice.bearer, alice.view.csrf_token,
            CredentialWrite(
                operation_id=uuid4(), key=KEY,
                expected_revision=verified.revision,
            ),
        )

    assert service.credential(alice.bearer) == verified
    with service.engine.begin() as conn:
        count = conn.execute(sa.select(chat.limits.c.count).where(
            chat.limits.c.account_id == alice.view.account.id,
            chat.limits.c.kind == "credential",
        )).scalar_one()
    assert count == CREDENTIAL_WINDOW_LIMIT - 1


def test_verified_credential_survives_service_reload(chat_env):
    service, alice, _, _ = chat_env
    verified = connect_key(service, alice)
    reloaded = ChatService(
        service.auth, service.policy, FakeDeepSeekProvider(),
        clock=service.clock, media_store=service.media_store,
    )
    current = reloaded.credential(alice.bearer)
    assert current == verified
    assert current.configured and current.enabled and current.verified
