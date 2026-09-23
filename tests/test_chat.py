"""CHAT-DEEPSEEK-001 domain: credential boundary, durable request identity and context."""
from __future__ import annotations

import base64
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.accounts import tables as accounts
from izo.accounts.schemas import RegisterInput
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.chat import tables as chat
from izo.chat.credentials import decrypt, encrypt
from izo.chat.provider import FakeDeepSeekProvider
from izo.chat.schemas import (
    CredentialCommand, CredentialWrite, RequestCreate,
)
from izo.chat.service import ChatError, ChatService
from izo.chat.schemas import ChatSettings

PASSWORD = "synthetic-chat-password-only"
KEY = "x" * 32


def root_key() -> str:
    return base64.urlsafe_b64encode(b"x" * 32).decode("ascii").rstrip("=")


@pytest.fixture
def chat_env(tmp_path):
    engine = sa.create_engine(
        "sqlite:///" + str(tmp_path / "chat.sqlite"),
        connect_args={"check_same_thread": False},
    )

    @sa.event.listens_for(engine, "connect")
    def connect(db, _):
        db.execute("PRAGMA foreign_keys=ON")

    accounts.metadata.create_all(engine)
    chat.metadata.create_all(engine, tables=list(chat.TABLES))
    clock = [20_000]
    auth = AuthService(
        engine,
        AuthSettings(
            registration="open", rate_secret="chat-test-rate-" * 4,
            login_limit=100, network_limit=1000,
        ),
        clock=lambda: clock[0],
    )
    alice = auth.register(
        RegisterInput(
            email="alice@example.invalid", display_name="Alice",
            password=PASSWORD,
        ),
        "isolated", "test",
    )
    bob = auth.register(
        RegisterInput(
            email="bob@example.invalid", display_name="Bob",
            password=PASSWORD,
        ),
        "isolated", "test",
    )
    policy = ChatSettings(
        root_key=root_key(),
        preview_account_emails="alice@example.invalid,bob@example.invalid",
    )
    service = ChatService(auth, policy, FakeDeepSeekProvider(), clock=lambda: clock[0])
    yield service, alice, bob, clock
    engine.dispose()


def connect_key(service, receipt):
    saved = service.save_credential(
        receipt.bearer, receipt.view.csrf_token,
        CredentialWrite(operation_id=uuid4(), key=KEY),
    )
    return service.verify_credential(
        receipt.bearer, receipt.view.csrf_token,
        CredentialCommand(
            operation_id=uuid4(), expected_revision=saved.revision,
        ),
    )
def request(service, receipt, thread_id, text, model="deepseek-flash", request_id=None):
    return service.create_request(
        receipt.bearer, receipt.view.csrf_token, thread_id,
        RequestCreate(
            request_id=request_id or uuid4(), text=text, model=model,
        ),
    )


def test_key_is_aad_bound_and_not_plaintext_in_database(chat_env):
    service, alice, bob, _ = chat_env
    verified = connect_key(service, alice)
    assert verified.verified and verified.generation == 1

    with service.engine.begin() as conn:
        row = conn.execute(sa.select(chat.connections).where(
            chat.connections.c.account_id == alice.view.account.id,
        )).mappings().one()
        assert KEY.encode() not in row["ciphertext"]
        assert KEY.encode() not in row["nonce"]
        copied_nonce, copied_ciphertext = row["nonce"], row["ciphertext"]

    bob_connection = uuid4()
    with pytest.raises(Exception):
        decrypt(
            service.policy.root_key_bytes(),
            bob.view.account.id, bob_connection, 1,
            copied_nonce, copied_ciphertext,
        )


def test_credential_idempotency_revision_and_disable(chat_env):
    service, alice, _, _ = chat_env
    op = uuid4()
    first = service.save_credential(
        alice.bearer, alice.view.csrf_token,
        CredentialWrite(operation_id=op, key=KEY),
    )
    replay = service.save_credential(
        alice.bearer, alice.view.csrf_token,
        CredentialWrite(operation_id=op, key=KEY),
    )
    assert replay == first

    with pytest.raises(ChatError, match="operation_conflict"):
        service.save_credential(
            alice.bearer, alice.view.csrf_token,
            CredentialWrite(
                operation_id=op, key="sk-test-different-key",
            ),
        )

    verified = service.verify_credential(
        alice.bearer, alice.view.csrf_token,
        CredentialCommand(
            operation_id=uuid4(), expected_revision=first.revision,
        ),
    )
    disabled = service.disable_credential(
        alice.bearer, alice.view.csrf_token,
        CredentialCommand(
            operation_id=uuid4(), expected_revision=verified.revision,
        ),
    )
    assert disabled.configured and not disabled.enabled and not disabled.verified


def test_request_replay_conflict_context_and_reload(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(
        alice.bearer, alice.view.csrf_token, None)

    stable_id = uuid4()
    first = request(
        service, alice, thread.id, "Первый вопрос",
        request_id=stable_id,
    )
    replay = request(
        service, alice, thread.id, "Первый вопрос",
        request_id=stable_id,
    )
    assert replay.id == first.id

    with pytest.raises(ChatError, match="request_conflict"):
        request(
            service, alice, thread.id, "Другой текст",
            request_id=stable_id,
        )

    events = "".join(service.stream_events(alice.bearer, first.id))
    assert "message.done" in events
    detail = service.thread_detail(alice.bearer, thread.id)
    assert [m.role for m in detail.messages] == ["user", "assistant"]
    assert detail.messages[-1].state == "complete"
    assert "Первый вопрос" in detail.messages[-1].content

    second = request(service, alice, thread.id, "Уточни это")
    events = "".join(service.stream_events(alice.bearer, second.id))
    assert "message.done" in events
    reloaded = service.thread_detail(alice.bearer, thread.id)
    assert len(reloaded.messages) == 4
    assert "Контекст: Первый вопрос" in reloaded.messages[-1].content
def test_cross_account_thread_request_and_connection_are_hidden(chat_env):
    service, alice, bob, _ = chat_env
    connect_key(service, alice)
    connect_key(service, bob)
    thread = service.create_thread(
        alice.bearer, alice.view.csrf_token, "private")
    created = request(service, alice, thread.id, "secret")

    with pytest.raises(ChatError, match="thread_not_found"):
        service.thread_detail(bob.bearer, thread.id)
    with pytest.raises(ChatError, match="request_not_found"):
        service.request(bob.bearer, created.id)
    with pytest.raises(ChatError, match="thread_not_found"):
        request(service, bob, thread.id, "steal")


def test_pending_stop_never_calls_provider(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(
        alice.bearer, alice.view.csrf_token, None)
    created = request(service, alice, thread.id, "stop before stream")
    stopped = service.stop(
        alice.bearer, alice.view.csrf_token, created.id)
    assert stopped.state == "stopped"
    events = "".join(service.stream_events(alice.bearer, created.id))
    assert "message.interrupted" in events
    detail = service.thread_detail(alice.bearer, thread.id)
    assert detail.messages[-1].state == "stopped"


def test_restart_marks_unfinished_stream_interrupted_without_resubmit(chat_env):
    service, alice, _, clock = chat_env
    connect_key(service, alice)
    thread = service.create_thread(
        alice.bearer, alice.view.csrf_token, None)
    created = request(service, alice, thread.id, "crash")

    with service.engine.begin() as conn:
        conn.execute(sa.update(chat.requests).where(
            chat.requests.c.id == created.id).values(state="streaming"))
    restarted = ChatService(
        service.auth, service.policy, FakeDeepSeekProvider(),
        clock=lambda: clock[0],
    )
    state = restarted.request(alice.bearer, created.id)
    assert state.state == "interrupted"
    detail = restarted.thread_detail(alice.bearer, thread.id)
    assert detail.messages[-1].state == "interrupted"


def test_encrypt_roundtrip_requires_exact_owner_context():
    root = b"k" * 32
    account, connection = uuid4(), uuid4()
    nonce, ciphertext = encrypt(root, account, connection, 3, KEY)
    assert decrypt(root, account, connection, 3, nonce, ciphertext) == KEY
    with pytest.raises(Exception):
        decrypt(root, uuid4(), connection, 3, nonce, ciphertext)

@pytest.mark.parametrize('boundary', ['start', 'partial', 'stop-before', 'stop-partial'])
def test_stream_stop_and_disconnect_boundaries(chat_env, boundary):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    created = request(service, alice, thread.id, 'bounded disconnect and Stop')
    stream = service.stream_events(alice.bearer, created.id)
    if boundary == 'stop-before':
        service.stop(alice.bearer, alice.view.csrf_token, created.id)
    else:
        assert 'message.start' in next(stream)
        if boundary in {'partial', 'stop-partial'}:
            assert 'text.delta' in next(stream)
    if boundary.startswith('stop'):
        service.stop(alice.bearer, alice.view.csrf_token, created.id)
        assert 'message.interrupted' in ''.join(stream)
        expected = 'stopped'
    else:
        stream.close()
        expected = 'interrupted'
    assert service.request(alice.bearer, created.id).state == expected
    assistant = service.thread_detail(alice.bearer, thread.id).messages[-1]
    assert assistant.state == expected
    assert bool(assistant.content) == (boundary in {'partial', 'stop-partial'})

def test_expired_unconsumed_claim_is_reconciled_without_new_execution(chat_env):
    service, alice, _, clock = chat_env
    connect_key(service, alice)
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    created = request(service, alice, thread.id, 'expire before consumer starts')
    unconsumed = service.stream_events(alice.bearer, created.id)
    clock[0] = created.deadline_at + 6
    events = ''.join(service.stream_events(alice.bearer, created.id))
    assert 'message.interrupted' in events and 'text.delta' not in events
    assert service.request(alice.bearer, created.id).state == 'interrupted'
    unconsumed.close()


def test_late_stream_finish_cannot_report_success_over_durable_interruption(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    created = request(service, alice, thread.id, 'competing terminal transition')
    stream = service.stream_events(alice.bearer, created.id)
    next(stream)
    next(stream)
    service._finish(created.id, 'interrupted', 'request_expired', 'persisted partial')
    events = ''.join(stream)
    assert 'message.done' not in events and 'message.interrupted' in events
    assert service.request(alice.bearer, created.id).state == 'interrupted'
