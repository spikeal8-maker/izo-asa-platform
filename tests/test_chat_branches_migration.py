"""Frozen 0019 retention and real PostgreSQL branch admission/constraint races."""
from contextlib import contextmanager

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from izo.chat import tables as t
from test_chat import chat_env, connect_key, new_thread, request
from test_chat_branches import durable_rows, edit, edit_command, send, switch
from test_chat_graph_context import finish
from test_chat_graph_requests import prepare, regenerate


@contextmanager
def migration_connection(service):
    with service.engine.connect() as conn:
        sqlite = conn.dialect.name == "sqlite"
        if sqlite:
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conn.commit()
        try:
            with conn.begin():
                yield conn
                if sqlite:
                    assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        finally:
            if sqlite:
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
                conn.commit()
                assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
                conn.commit()


def drop_graph_tables(conn):
    names = sa.inspect(conn).get_table_names()
    if conn.dialect.name == "postgresql":
        for table in (t.branches, t.attempts):
            for fk in sa.inspect(conn).get_foreign_keys(table.name):
                if fk["name"] in {"chat_branch_fork_turn", "chat_branch_fork_attempt",
                                  "chat_attempt_source_membership"}:
                    conn.exec_driver_sql(f'ALTER TABLE {table.name} DROP CONSTRAINT {fk["name"]}')
    for table in (t.contexts, t.selections, t.branch_attempts, t.attempts,
                  t.branch_turns, t.turns, t.graphs, t.branches):
        if table.name in names:
            table.drop(conn)


def upgrade_graph(service):
    from test_chat_graph_migration import migration, old_rows
    module = migration("0019_chat_message_branches")
    assert module.down_revision == "0018_chat_conversation_graph"
    with migration_connection(service) as conn:
        physical = old_rows(conn)
        old = {table.name: [dict(row) for row in conn.execute(sa.select(table)
            .order_by(*table.primary_key.columns)).mappings()] for table in
            (t.branches, t.graphs, t.turns, t.attempts, t.selections, t.contexts)}
        context_bytes = conn.exec_driver_sql(
            "SELECT request_id, CAST(snapshot AS TEXT), digest FROM chat_request_contexts ORDER BY request_id").all()
        drop_graph_tables(conn)
        metadata = sa.MetaData()
        for table in (t.threads, t.requests, t.messages):
            table.to_metadata(metadata)
        graphs, branches, turns, attempts, selections, contexts = migration()._frozen_tables(metadata)
        for table in (branches, graphs, turns, attempts, selections, contexts):
            table.create(conn)
            rows = [{key: value for key, value in row.items() if key in table.c} for row in old[table.name]]
            if table is attempts:
                rows.sort(key=lambda row: row["ordinal"])
            if rows:
                conn.execute(sa.insert(table), rows)
        retained = {table.name: [dict(row) for row in conn.execute(sa.select(table)
            .order_by(*table.primary_key.columns)).mappings()] for table in
            (branches, graphs, turns, attempts, selections, contexts)}
        module.op = Operations(MigrationContext.configure(conn))
        module.upgrade()
        assert old_rows(conn) == physical
        for table in (branches, graphs, turns, attempts, selections, contexts):
            assert [dict(row) for row in conn.execute(sa.select(table)
                .order_by(*table.primary_key.columns)).mappings()] == retained[table.name]
        assert conn.exec_driver_sql(
            "SELECT request_id, CAST(snapshot AS TEXT), digest FROM chat_request_contexts ORDER BY request_id").all() == context_bytes
        assert set(conn.execute(sa.select(t.branch_turns.c.branch_id, t.branch_turns.c.turn_id))) == {
            (row["branch_id"], row["id"]) for row in old[t.turns.name]}
        assert set(conn.execute(sa.select(t.branch_attempts.c.branch_id, t.branch_attempts.c.attempt_id))) == {
            (row["branch_id"], row["id"]) for row in old[t.attempts.name]}
    return module


def test_0019_retains_recorded_graph_and_enables_branch_local_selection(chat_env):
    service, alice, _, _ = chat_env
    thread, _, _ = prepare(service, alice)
    second, _ = regenerate(service, alice, thread.id)
    finish(service, alice, second.request)
    suffix = request(service, alice, thread.id, "Suffix retained")
    finish(service, alice, suffix)
    service.rename_thread(alice.bearer, alice.view.csrf_token, thread.id, "Immutable title")
    module = upgrade_graph(service)
    accepted, _, _ = edit(service, alice, thread.id, "New child")
    finish(service, alice, accepted.request)
    restored = switch(service, alice, thread.id, thread.id)
    assert restored.turns[0].selected_attempt_id == second.request.id
    assert restored.turns[-1].user_message.content == "Suffix retained"
    assert restored.thread.title == "Immutable title"
    with pytest.raises(RuntimeError, match="forward migration"):
        module.downgrade()


def test_0019_rejects_cross_thread_membership_and_invalid_ancestry(chat_env):
    service, alice, _, _ = chat_env
    thread, original, _ = prepare(service, alice)
    other = new_thread(service, alice)
    foreign = request(service, alice, other.id, "Foreign")
    finish(service, alice, foreign)
    upgrade_graph(service)
    child, _, _ = edit(service, alice, thread.id, "Edited")
    changes = [
        sa.update(t.branch_turns).where(t.branch_turns.c.branch_id == child.created_branch.id).values(thread_id=other.id),
        sa.update(t.branch_attempts).where(t.branch_attempts.c.branch_id == child.created_branch.id).values(attempt_id=foreign.id),
        sa.update(t.branches).where(t.branches.c.id == child.created_branch.id).values(parent_branch_id=other.id),
        sa.update(t.branches).where(t.branches.c.id == child.created_branch.id).values(fork_source_attempt_id=foreign.id),
        sa.update(t.branches).where(t.branches.c.id == child.created_branch.id).values(branch_ordinal=1),
        sa.update(t.branches).where(t.branches.c.id == thread.id).values(parent_branch_id=thread.id),
    ]
    before = durable_rows(service)
    for statement in changes:
        with pytest.raises(IntegrityError):
            with service.engine.begin() as conn:
                conn.execute(statement)
    assert durable_rows(service) == before
