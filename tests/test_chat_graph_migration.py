"""Forward Graph retention and relational boundaries on the unit database."""
import importlib.util
from contextlib import contextmanager
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from izo.chat import tables as t
from test_chat import chat_env, connect_key, new_thread, request
from test_chat_vision import vision_env, asset, submit


def migration(name="0018_chat_conversation_graph"):
    path = Path(__file__).resolve().parents[1] / f"apps/api/migrations/versions/{name}.py"
    spec = importlib.util.spec_from_file_location("graph_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def old_rows(conn):
    # Physical IDs, message bytes, manual titles and private attachments.
    tables = (t.connections, t.threads, t.requests, t.messages, t.attachments, t.limits)
    return {table.name: [dict(row) for row in conn.execute(sa.select(table)
            .order_by(*table.primary_key.columns)).mappings()] for table in tables}


def upgrade_legacy(service):
    from test_chat_branches_migration import drop_graph_tables, migration_connection
    module = migration()
    assert module.down_revision == "0017_chat_manual_title"
    with migration_connection(service) as conn:
        before = old_rows(conn)
        # Recreate only Graph; all original physical rows must survive both upgrades.
        drop_graph_tables(conn)
        for name in ("ux_chat_request_graph_identity", "ux_chat_message_graph_role",
                     "ux_chat_message_graph_request"):
            conn.exec_driver_sql(f"DROP INDEX {name}")
        module.op = Operations(MigrationContext.configure(conn))
        module.upgrade()
        branch_upgrade = migration("0019_chat_message_branches")
        branch_upgrade.op = module.op
        branch_upgrade.upgrade()
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


@contextmanager
def pg_environment():
    """Standalone isolated runner: default pytest never changes its no-network fixture."""
    import os
    from uuid import uuid4
    from izo.config import Settings
    from izo.accounts.schemas import RegisterInput
    from izo.accounts.service import AuthService
    from izo.accounts.settings import AuthSettings
    from izo.chat.schemas import ChatSettings
    from izo.chat.service import ChatService
    from test_chat import PASSWORD, root_key
    from test_chat_graph_requests import RecordingProvider
    from test_chat_graph_http import pg_bootstrap_catalog
    from test_chat_vision import Objects
    cfg = Settings()
    if cfg.environment != "test" or os.environ.get("IZO_CHAT_GRAPH_ACCEPTANCE") != "isolated":
        raise RuntimeError("PostgreSQL graph checks require explicit isolated/test opt-in")
    url = sa.URL.create("postgresql+psycopg", username=cfg.pg_user,
        password=cfg.pg_password.get_secret_value(), host=cfg.pg_host,
        port=cfg.pg_port, database=cfg.pg_database)
    schema = "izo_graph_" + uuid4().hex
    control = sa.create_engine(url)
    engine = None
    try:
        with control.begin() as conn:
            conn.execute(sa.schema.CreateSchema(schema))
        engine = sa.create_engine(url, pool_size=8, max_overflow=0, connect_args={"options":
            f"-c search_path={schema} -c application_name={schema} -c statement_timeout=15000 -c lock_timeout=12000"})
        with engine.begin() as conn:
            assert conn.exec_driver_sql("SHOW transaction_isolation").scalar_one() == "read committed"
            assert conn.exec_driver_sql("SELECT current_schema()").scalar_one() == schema
        pg_bootstrap_catalog(engine)
        t.media_assets.create(engine)
        t.metadata.create_all(engine, tables=list(t.TABLES))
        clock = [20_000]
        auth = AuthService(engine, AuthSettings(registration="open",
            rate_secret="pg-graph-synthetic-rate-" * 4, login_limit=100, network_limit=1000),
            clock=lambda: clock[0])
        owners = [auth.register(RegisterInput(email=email, display_name=email.split("@")[0],
            password=PASSWORD), "isolated", "test") for email in (
                "alice@example.invalid", "bob@example.invalid")]
        service = ChatService(auth, ChatSettings(root_key=root_key(),
            preview_account_emails="alice@example.invalid,bob@example.invalid"),
            RecordingProvider(), clock=lambda: clock[0], media_store=Objects())
        service._graph_pg_label = schema
        yield service, *owners, clock
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as conn:
            conn.execute(sa.schema.DropSchema(schema, cascade=True, if_exists=True))
        control.dispose()


def run_postgres():
    from test_chat_graph_context import pg_completion_and_projection_locks
    from test_chat_graph_context import test_next_send_freezes_chosen_answer_at_admission_not_later_selection
    from test_chat_graph_context import test_regenerating_earlier_turn_excludes_own_alternatives_and_later_suffix
    from test_chat_graph_requests import pg_command_races
    from test_chat_graph_requests import test_failed_regenerate_keeps_selection_and_unknown_blocks_new_execution
    from test_chat_graph_requests import test_pending_stop_and_late_partial_do_not_replace_completed_content
    cases = [
        ("migration_retention", lambda e: (connect_key(e[0], e[1]),
            test_forward_backfill_retains_messages_titles_images_and_paid_evidence((*e, e[0].media_store)))),
        ("same_thread_context_fk", test_context_must_belong_to_requests_own_turn_inside_same_thread),
        ("cross_thread_fk", test_database_rejects_foreign_branch_turn_and_selection),
        ("message_role_fk", test_database_rejects_user_assistant_role_swap),
        ("null_revision", lambda e: test_captured_context_requires_nonnull_nonnegative_revision(e, None)),
        ("negative_revision", lambda e: test_captured_context_requires_nonnull_nonnegative_revision(e, -1)),
        ("concurrent_request_identity", pg_command_races),
        ("thread_request_order_and_projection", pg_completion_and_projection_locks),
        ("frozen_selection_context", test_next_send_freezes_chosen_answer_at_admission_not_later_selection),
        ("earlier_turn_context", test_regenerating_earlier_turn_excludes_own_alternatives_and_later_suffix),
        ("stopped_and_late_partial", test_pending_stop_and_late_partial_do_not_replace_completed_content),
        ("known_rejection", lambda e: test_failed_regenerate_keeps_selection_and_unknown_blocks_new_execution(
            e, "provider_rejected")),
        ("unknown_paid_barrier", lambda e: test_failed_regenerate_keeps_selection_and_unknown_blocks_new_execution(
            e, "provider_connection_failed")),
    ]
    for name, check in cases:
        with pg_environment() as environment:
            check(environment)
        print("POSTGRES_PASS " + name, flush=True)
    print(f"POSTGRES_GRAPH_PASS cases={len(cases)}", flush=True)


if __name__ == "__main__":
    run_postgres()
