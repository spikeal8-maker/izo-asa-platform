"""Frozen 0019 retention and PostgreSQL branch races."""
from contextlib import contextmanager
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from izo.chat import tables as t
from izo.chat.branches import branch_page, change_branch
from izo.chat.graph_requests import admit_request
from izo.chat.graph_schemas import BranchSelection
from izo.chat.history_pages import graph_page
from izo.chat.service import ChatError
from test_chat import chat_env, new_thread, request
from test_chat_branches import durable_rows, edit, edit_command, switch
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


def test_0019_retains_recorded_graph_and_branch_selection(chat_env):
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


def test_0019_rejects_foreign_membership_and_ancestry(chat_env):
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


def pg_branch_contenders(environment, mode):
    from izo.chat.schemas import RequestCreate
    from test_chat_graph_http import pg_parallel
    service, alice, _, _ = environment
    thread, _, _ = prepare(service, alice)
    child, _, _ = edit(service, alice, thread.id, "Existing child")
    finish(service, alice, child.request)
    switch(service, alice, thread.id, thread.id)
    source, command = edit_command(service, alice, thread.id,
        "Исходный вопрос" if mode == "unchanged" else "Concurrent edit")
    def invoke(value):
        return lambda: admit_request(service, alice.bearer, alice.view.csrf_token,
            thread.id, value, source, edit=True)
    second = invoke(command if mode == "same" else command.model_copy(update={"request_id": uuid4()}))
    if mode == "send":
        body = RequestCreate(request_id=uuid4(), model="deepseek-flash", text="Concurrent send",
            branch_id=command.branch_id, expected_revision=command.expected_revision)
        second = lambda: service.create_request(alice.bearer, alice.view.csrf_token, thread.id, body)
    if mode == "switch":
        body = BranchSelection(branch_id=command.branch_id, expected_revision=command.expected_revision,
            target_branch_id=child.created_branch.id)
        second = lambda: change_branch(service, alice.bearer, alice.view.csrf_token, thread.id, body)
    before = durable_rows(service)
    results = pg_parallel(service, thread.id, [invoke(command), second])
    if mode == "unchanged":
        assert results == ["message_unchanged", "message_unchanged"]
        assert durable_rows(service) == before
    elif mode == "same":
        assert results[0] == results[1]
        assert len(durable_rows(service)[t.branches.name]) == len(before[t.branches.name]) + 1
        assert len(durable_rows(service)[t.requests.name]) == len(before[t.requests.name]) + 1
    else:
        assert sum(isinstance(result, str) for result in results) == 1
        assert "graph_revision_conflict" in results


def test_edit_rollback_retains_all_rows(chat_env):
    from izo.chat import conversations
    service, alice, _, _ = chat_env
    thread, _, _ = prepare(service, alice)
    before = durable_rows(service)
    def fail(*_):
        raise ChatError(422, "injected_context_write_failure")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(conversations, "freeze_context", fail)
        with pytest.raises(ChatError, match="injected_context_write_failure"):
            edit(service, alice, thread.id, "Rollback this")
    assert durable_rows(service) == before


def test_branch_and_turn_paging_revision_fences(chat_env):
    from test_chat_graph_requests import select
    from izo.chat.history_pages import attempt_page
    service, alice, _, clock = chat_env
    thread, first, _ = prepare(service, alice)
    for index in range(51):
        clock[0] += 61
        finish(service, alice, request(service, alice, thread.id, f"Turn {index}"))
    page = graph_page(service, alice.bearer, thread.id)
    older = graph_page(service, alice.bearer, thread.id, page.next_before_turn_sequence)
    assert len(page.turns) == 50 and len(older.turns) == 2
    clock[0] += 61
    child, _, _ = edit(service, alice, thread.id, "Fork last")
    finish(service, alice, child.request)
    switch(service, alice, thread.id, thread.id)
    clock[0] += 61
    alternate, _ = regenerate(service, alice, thread.id, older.turns[0].id)
    finish(service, alice, alternate.request)
    newest = graph_page(service, alice.bearer, thread.id)
    select(service, alice, thread.id, older.turns[0].id, first.id)
    stale_range = graph_page(service, alice.bearer, thread.id, newest.next_before_turn_sequence)
    assert newest.revision != stale_range.revision
    with pytest.raises(ChatError, match="graph_revision_conflict"):
        graph_page(service, alice.bearer, thread.id, branch_id=child.created_branch.id)
    with pytest.raises(ChatError, match="graph_revision_conflict"):
        attempt_page(service, alice.bearer, thread.id, older.turns[0].id, branch_id=child.created_branch.id)
    # Metadata cursor boundary; no generation is needed for listing.
    with service.engine.begin() as conn:
        template = dict(conn.execute(sa.select(t.branches).where(t.branches.c.id == child.created_branch.id)).mappings().one())
        conn.execute(sa.insert(t.branches), [{**template, "id": uuid4(), "branch_ordinal": n} for n in range(3, 54)])
    latest = branch_page(service, alice.bearer, thread.id)
    oldest = branch_page(service, alice.bearer, thread.id, latest.next_before_branch_ordinal)
    assert [branch.branch_ordinal for branch in latest.branches] == list(range(53, 3, -1))
    assert [branch.branch_ordinal for branch in oldest.branches] == [3, 2, 1]
    assert latest.active_branch.id == thread.id and oldest.next_before_branch_ordinal is None


def run_postgres():
    from test_chat_graph_migration import pg_environment
    from test_chat_branches import test_inherited_manual_selection_and_execution_are_branch_local
    cases = [("branches_0019_retention", test_0019_retains_recorded_graph_and_branch_selection),
        ("branches_relational_boundaries", test_0019_rejects_foreign_membership_and_ancestry),
        ("branches_inherited_selection", test_inherited_manual_selection_and_execution_are_branch_local),
        ("branches_atomic_rollback", test_edit_rollback_retains_all_rows)]
    cases += [("branches_race_" + mode, lambda e, m=mode: pg_branch_contenders(e, m))
              for mode in ("same", "distinct", "unchanged", "send", "switch")]
    for name, check in cases:
        with pg_environment() as environment:
            check(environment)
        print("POSTGRES_PASS " + name, flush=True)
    print(f"POSTGRES_BRANCH_PASS cases={len(cases)}", flush=True)
