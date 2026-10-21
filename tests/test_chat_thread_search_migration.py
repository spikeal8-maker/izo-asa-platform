"""Forward 0020 key backfill retains all existing title and Conversation Graph evidence."""
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from izo.chat import tables as t
from izo.chat import thread_title_search_v1 as matcher
from test_chat import chat_env
from test_chat_branches import edit
from test_chat_branches_migration import migration_connection
from test_chat_graph_context import finish
from test_chat_graph_migration import migration
from test_chat_graph_requests import prepare


def snapshot(conn):
    return {table.name: conn.execute(sa.select(
        *(column for column in table.c if column.name != "title_search_key"))
        .order_by(*table.primary_key.columns)).mappings().all() for table in t.TABLES}


def retained_backfill(environment):
    service, alice, _, _ = environment
    thread, _, _ = prepare(service, alice)
    child, _, _ = edit(service, alice, thread.id, "Retained child")
    finish(service, alice, child.request)
    service.rename_thread(alice.bearer, alice.view.csrf_token, thread.id, "İ ΟΣ manual")
    with service.engine.begin() as conn:
        # More than one bounded migration batch, alongside a real branched conversation.
        conn.execute(sa.insert(t.threads), [{"id": UUID(int=i + 1),
            "account_id": alice.view.account.id, "title": "İ" * 120,
            "title_search_key": "stale", "next_sequence": 1,
            "created_at": 1, "updated_at": 1} for i in range(503)])
    module = migration("0020_chat_thread_title_search")
    assert module.down_revision == "0019_chat_message_branches"
    with migration_connection(service) as conn:
        before = snapshot(conn)
        indexes = {i["name"]: i["column_names"] for i in sa.inspect(conn).get_indexes("chat_threads")}
        context_bytes = conn.exec_driver_sql(
            "SELECT request_id, CAST(snapshot AS TEXT), digest FROM chat_request_contexts ORDER BY request_id").all()
        conn.exec_driver_sql("ALTER TABLE chat_threads DROP COLUMN title_search_key")
        module.op = Operations(MigrationContext.configure(conn))
        module.upgrade()
        assert snapshot(conn) == before
        assert {i["name"]: i["column_names"] for i in sa.inspect(conn).get_indexes("chat_threads")} == indexes
        assert conn.exec_driver_sql(
            "SELECT request_id, CAST(snapshot AS TEXT), digest FROM chat_request_contexts ORDER BY request_id").all() == context_bytes
        rows = conn.execute(sa.select(t.threads)).mappings().all()
        assert len(rows) == 504
        assert all(row["title_search_key"] == matcher.title_key(row["title"]) for row in rows)
        assert max(len(row["title_search_key"]) for row in rows) == 240
        column = next(c for c in sa.inspect(conn).get_columns("chat_threads") if c["name"] == "title_search_key")
        assert column["nullable"] is False and column["default"] is None
    assert service.list_threads(alice.bearer, q="manual").threads[0].id == thread.id
    with pytest.raises(RuntimeError, match="forward migration"):
        module.downgrade()


def test_forward_backfill_retains_graph_titles_context_and_rows(chat_env):
    retained_backfill(chat_env)


def test_migration_rejects_unknown_unicode_runtime_before_ddl(monkeypatch):
    module = migration("0020_chat_thread_title_search")
    monkeypatch.setattr(matcher.unicodedata, "unidata_version", "16.0.0")
    def forbidden():
        raise AssertionError("unversioned matcher reached database")
    monkeypatch.setattr(module.op, "get_bind", forbidden)
    with pytest.raises(RuntimeError, match="Unicode 15.1"):
        module.upgrade()
