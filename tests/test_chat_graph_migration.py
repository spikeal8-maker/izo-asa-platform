"""Forward Graph retention and relational boundaries on the unit database."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from izo.chat import tables as t
from test_chat import chat_env, connect_key, new_thread, request
from test_chat_vision import vision_env, asset, submit


def migration():
    path = Path(__file__).resolve().parents[1] / "apps/api/migrations/versions/0018_chat_conversation_graph.py"
    spec = importlib.util.spec_from_file_location("graph_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def old_rows(conn):
    # Graph adds only indexes to these pre-existing tables. Values include
    # original IDs, message bytes, manual-title flags and private attachments.
    tables = (t.connections, t.threads, t.requests, t.messages, t.attachments, t.limits)
    return {table.name: [dict(row) for row in conn.execute(sa.select(table)
            .order_by(*table.primary_key.columns)).mappings()] for table in tables}


def upgrade_legacy(service):
    module = migration()
    assert module.down_revision == "0017_chat_manual_title"
    with service.engine.begin() as conn:
        before = old_rows(conn)
        # Restore the precise pre-0018 relational shape while retaining the
        # admitted legacy rows; no original table or data is dropped/recreated.
        for table in (t.contexts, t.selections, t.attempts, t.turns, t.graphs, t.branches):
            table.drop(conn)
        for name in ("ux_chat_request_graph_identity", "ux_chat_message_graph_role",
                     "ux_chat_message_graph_request"):
            conn.exec_driver_sql(f"DROP INDEX {name}")
        module.op = Operations(MigrationContext.configure(conn))
        module.upgrade()
        assert old_rows(conn) == before
    return module


def test_forward_backfill_retains_messages_titles_images_and_paid_evidence(vision_env):
    service, alice, _, _, objects = vision_env
    image_id = asset(service, alice, objects)
    thread = new_thread(service, alice)
    service.rename_thread(alice.bearer, alice.view.csrf_token, thread.id, "Выбранное вручную")
    completed = submit(service, alice, thread, [image_id], text="Старое изображение")
    assert "message.done" in "".join(service.stream_events(alice.bearer, completed.id))
    pending = request(service, alice, thread.id, "Ещё не отправлено провайдеру")
    other = new_thread(service, alice)
    unknown = request(service, alice, other.id, "Неизвестный старый исход")
    with service.engine.begin() as conn:
        conn.execute(sa.update(t.requests).where(t.requests.c.id == unknown.id).values(
            state="interrupted", error_code="provider_outcome_unknown"))
        conn.execute(sa.update(t.messages).where(t.messages.c.request_id == unknown.id,
            t.messages.c.role == "assistant").values(state="interrupted"))
    module = upgrade_legacy(service)
    with service.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.graphs)).scalar_one() == 2
        assert conn.execute(sa.select(sa.func.count()).select_from(t.turns)).scalar_one() == 3
        assert set(conn.execute(sa.select(t.attempts.c.id)).scalars()) == {completed.id, pending.id, unknown.id}
        assert conn.execute(sa.select(t.selections.c.attempt_id)).scalars().all() == [completed.id]
        contexts = conn.execute(sa.select(t.contexts)).mappings().all()
        assert len(contexts) == 3
        assert all(row["provenance"] == "legacy_unrecorded" and row["snapshot"] is None
                   and row["digest"] is None and row["revision"] is None for row in contexts)
    with pytest.raises(RuntimeError, match="forward migration"):
        module.downgrade()


def _two_threads(service, alice):
    connect_key(service, alice)
    pairs = []
    for text in ("Первый", "Второй"):
        thread = new_thread(service, alice)
        created = request(service, alice, thread.id, text)
        assert "message.done" in "".join(service.stream_events(alice.bearer, created.id))
        pairs.append((thread, created))
    upgrade_legacy(service)
    return pairs


def test_database_rejects_foreign_branch_turn_and_selection(chat_env):
    service, alice, _, _ = chat_env
    (first, first_request), (second, second_request) = _two_threads(service, alice)
    with service.engine.begin() as conn:
        turn = conn.execute(sa.select(t.turns).where(t.turns.c.thread_id == first.id)).mappings().one()
    changes = (
        sa.update(t.graphs).where(t.graphs.c.thread_id == first.id).values(active_branch_id=second.id),
        sa.update(t.turns).where(t.turns.c.id == turn["id"]).values(branch_id=second.id),
        sa.update(t.selections).where(t.selections.c.turn_id == turn["id"]).values(attempt_id=second_request.id),
        sa.update(t.attempts).where(t.attempts.c.id == first_request.id).values(source_attempt_id=second_request.id),
    )
    for statement in changes:
        with pytest.raises(IntegrityError):
            with service.engine.begin() as conn:
                conn.execute(statement)


def test_database_rejects_user_assistant_role_swap(chat_env):
    service, alice, _, _ = chat_env
    (thread, created), _ = _two_threads(service, alice)
    with service.engine.begin() as conn:
        messages = conn.execute(sa.select(t.messages).where(
            t.messages.c.request_id == created.id).order_by(t.messages.c.sequence)).mappings().all()
    changes = (
        sa.update(t.turns).where(t.turns.c.thread_id == thread.id).values(user_message_id=messages[1]["id"]),
        sa.update(t.attempts).where(t.attempts.c.id == created.id).values(assistant_message_id=messages[0]["id"]),
    )
    for statement in changes:
        with pytest.raises(IntegrityError):
            with service.engine.begin() as conn:
                conn.execute(statement)


def test_context_must_belong_to_requests_own_turn_inside_same_thread(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = new_thread(service, alice)
    first = request(service, alice, thread.id, "First turn")
    list(service.stream_events(alice.bearer, first.id))
    second = request(service, alice, thread.id, "Different turn in the same branch")
    upgrade_legacy(service)
    with service.engine.begin() as conn:
        second_turn = conn.execute(sa.select(t.attempts.c.turn_id).where(
            t.attempts.c.id == second.id)).scalar_one()
    with pytest.raises(IntegrityError):
        with service.engine.begin() as conn:
            conn.execute(sa.update(t.contexts).where(t.contexts.c.request_id == first.id)
                .values(turn_id=second_turn))


@pytest.mark.parametrize("invalid_revision", [None, -1])
def test_captured_context_requires_nonnull_nonnegative_revision(chat_env, invalid_revision):
    service, alice, _, _ = chat_env
    (thread, first), _ = _two_threads(service, alice)
    with pytest.raises(IntegrityError):
        with service.engine.begin() as conn:
            conn.execute(sa.update(t.contexts).where(t.contexts.c.request_id == first.id).values(
                provenance="admission", snapshot={"version": "test"}, digest="0" * 64,
                revision=invalid_revision))
