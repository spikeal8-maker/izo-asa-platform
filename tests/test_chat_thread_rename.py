"""Durable manual titles preserve ownership, message identity and paging."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from izo.chat import tables as chat
from izo.chat.execution import FakeDeepSeekProvider
from izo.chat.service import ChatError, ChatService
from test_chat import chat_env, connect_key, new_thread, request


def rename(service, receipt, thread_id, title):
    return service.rename_thread(receipt.bearer, receipt.view.csrf_token, thread_id, title)


def thread_row(service, thread_id):
    with service.engine.connect() as conn:
        return dict(conn.execute(sa.select(chat.threads).where(
            chat.threads.c.id == thread_id)).mappings().one())


def test_rename_is_durable_private_and_idempotent(chat_env):
    service, alice, _, clock = chat_env
    thread = new_thread(service, alice)
    clock[0] += 7
    saved = rename(service, alice, thread.id, " \ufeffМой проект 😀\u00a0 ")
    assert saved.title == "Мой проект 😀"
    assert saved.created_at == thread.created_at
    assert saved.updated_at == clock[0]
    assert "title_is_manual" not in saved.model_dump()
    row = thread_row(service, thread.id)
    assert row["title_is_manual"] and row["next_sequence"] == 1
    clock[0] += 2
    assert rename(service, alice, thread.id, saved.title) == saved
    assert thread_row(service, thread.id) == row
    restarted = ChatService(service.auth, service.policy, FakeDeepSeekProvider(),
                            clock=lambda: clock[0])
    assert restarted.thread_detail(alice.bearer, thread.id).thread == saved
    assert restarted.list_threads(alice.bearer).threads == [saved]
    assert restarted.credential(alice.bearer).configured is False


@pytest.mark.parametrize("rename_first", [True, False])
def test_manual_placeholder_survives_first_request_in_both_serial_orders(chat_env, rename_first):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = new_thread(service, alice)
    if rename_first:
        rename(service, alice, thread.id, "Новый чат")
    created = request(service, alice, thread.id, "Automatic first title")
    if not rename_first:
        assert service.thread_detail(alice.bearer, thread.id).thread.title == "Automatic first title"
        rename(service, alice, thread.id, "Новый чат")
    replay = request(service, alice, thread.id, "Automatic first title", request_id=created.id)
    assert replay == created
    assert "message.done" in "".join(service.stream_events(alice.bearer, created.id))
    detail = service.thread_detail(alice.bearer, thread.id)
    assert detail.thread.title == "Новый чат"
    assert [message.sequence for message in detail.messages] == [1, 2]
    assert all(message.request_id == created.id for message in detail.messages)
    assert thread_row(service, thread.id)["title_is_manual"]


@pytest.mark.parametrize("title", ["Новый чат", "custom title"])
def test_create_contract_and_automatic_title_remain_compatible(chat_env, title):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, title)
    request(service, alice, thread.id, "First message")
    expected = "First message" if title == "Новый чат" else title
    assert service.thread_detail(alice.bearer, thread.id).thread.title == expected
    assert thread_row(service, thread.id)["title_is_manual"] is False


@pytest.mark.parametrize("title", ["a" * 120, "😀" * 120, " \ufeff" + "я" * 120 + "\u3000"])
def test_title_limit_counts_unicode_code_points_after_trim(chat_env, title):
    service, alice, _, _ = chat_env
    saved = rename(service, alice, new_thread(service, alice).id, title)
    assert len(saved.title) == 120


def test_mixed_visible_title_is_not_treated_as_whitespace_only(chat_env):
    service, alice, _, _ = chat_env
    title = "\u0085\ufeffX\u0085"
    assert rename(service, alice, new_thread(service, alice).id, title).title == title


@pytest.mark.parametrize("title", ["", " \t\n\u3000", "\u0085", "\ufeff", " \ufeff\u0085 ",
    "\ufeff\x1c", "\u0085\ufeff\u0085", "\x1c\ufeff\x1c", "a" * 121,
    "😀" * 121, "private\x00title", "private\ud800title", "\udfff", None, 123, True, {}, []])
def test_invalid_domain_title_never_mutates_database(chat_env, title):
    service, alice, _, _ = chat_env
    thread = new_thread(service, alice)
    before = thread_row(service, thread.id)
    with pytest.raises(ChatError, match="invalid_input") as error:
        rename(service, alice, thread.id, title)
    assert error.value.status == 422
    assert thread_row(service, thread.id) == before


def test_foreign_and_missing_threads_have_same_error_and_no_mutation(chat_env):
    service, alice, bob, _ = chat_env
    thread = new_thread(service, alice)
    before = thread_row(service, thread.id)
    for thread_id in (thread.id, uuid4()):
        with pytest.raises(ChatError, match="thread_not_found") as error:
            rename(service, bob, thread_id, "stolen")
        assert error.value.status == 404
    assert thread_row(service, thread.id) == before


def test_rename_preserves_both_history_cursors_and_request_identity(chat_env):
    service, alice, _, clock = chat_env
    connect_key(service, alice)
    threads = [new_thread(service, alice) for _ in range(55)]
    first = service.list_threads(alice.bearer)
    older = service.list_threads(alice.bearer, first.next_cursor)
    thread_id = older.threads[-1].id
    created = request(service, alice, thread_id, "Message identity")
    assert "message.done" in "".join(service.stream_events(alice.bearer, created.id))
    detail = service.thread_detail(alice.bearer, thread_id)
    page = service.older_messages(alice.bearer, thread_id, 2)
    row = thread_row(service, thread_id)
    clock[0] += 10
    rename(service, alice, thread_id, "Renamed old conversation")
    after_first = service.list_threads(alice.bearer)
    after_older = service.list_threads(alice.bearer, first.next_cursor)
    assert first.next_cursor == after_first.next_cursor
    assert [item.id for item in first.threads] == [item.id for item in after_first.threads]
    assert [item.id for item in older.threads] == [item.id for item in after_older.threads]
    assert set(item.id for item in first.threads + older.threads) == set(item.id for item in threads)
    assert service.thread_detail(alice.bearer, thread_id).messages == detail.messages
    assert service.older_messages(alice.bearer, thread_id, 2) == page
    assert service.request(alice.bearer, created.id).id == created.id
    after = thread_row(service, thread_id)
    assert after["next_sequence"] == row["next_sequence"]
    assert after["created_at"] == row["created_at"]


def test_forward_migration_preserves_existing_titles_and_default(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "apps/api/migrations/versions/0017_chat_manual_title.py"
    spec = importlib.util.spec_from_file_location("chat_manual_title", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "0016_chat_thread_created_index"
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "before-rename.sqlite"))
    try:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE TABLE chat_threads (id INTEGER PRIMARY KEY, title VARCHAR(120) NOT NULL)"))
            conn.execute(sa.text("INSERT INTO chat_threads (id, title) VALUES (1, 'Existing title')"))
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(conn)))
            migration.upgrade()
            conn.execute(sa.text("INSERT INTO chat_threads (id, title) VALUES (2, 'Future title')"))
            rows = conn.execute(sa.text("SELECT title, title_is_manual FROM chat_threads ORDER BY id")).all()
            assert rows == [("Existing title", False), ("Future title", False)]
            marker = next(item for item in sa.inspect(conn).get_columns("chat_threads")
                          if item["name"] == "title_is_manual")
            assert marker["nullable"] is False
        with pytest.raises(RuntimeError, match="forward migration"):
            migration.downgrade()
    finally:
        engine.dispose()
