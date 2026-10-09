"""Account-owned thread history extends beyond the first 50 rows."""

import base64
import json
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from izo.chat import tables as chat
from izo.chat.credentials import ChatError
from test_chat import chat_env, new_thread


def test_thread_pages_have_stable_tie_order_and_owner_isolation(chat_env):
    service, alice, bob, clock = chat_env
    ids = [new_thread(service, alice).id for _ in range(105)]
    foreign = new_thread(service, bob).id
    seen = []
    cursor = None
    newer = None
    while True:
        page = service.list_threads(alice.bearer, cursor)
        seen.extend(item.id for item in page.threads)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
        if newer is None:
            unseen = min(ids)
            with service.engine.begin() as conn:
                conn.execute(sa.update(chat.threads).where(chat.threads.c.id == unseen)
                             .values(updated_at=clock[0] + 100))
            clock[0] += 1
            newer = new_thread(service, alice).id
    assert len(seen) == len(set(seen)) == 105
    assert set(seen) == set(ids)
    assert foreign not in seen
    assert newer not in seen  # a new row above the cursor cannot duplicate a later page
    assert service.thread_detail(alice.bearer, ids[0]).thread.id == ids[0]
    assert seen == sorted(ids, reverse=True)  # all rows share the same clock tick
    assert [item.id for item in service.list_threads(bob.bearer).threads] == [foreign]
    with pytest.raises(ChatError, match='invalid_thread_cursor'):
        service.list_threads(alice.bearer, 'not-a-cursor')
    for bad_id in (123, {}, None):
        payload = {'v': 1, 'created_at': clock[0], 'id': bad_id}
        malformed = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        with pytest.raises(ChatError, match='invalid_thread_cursor'):
            service.list_threads(alice.bearer, malformed)


def test_created_order_index_forward_migration(chat_env, monkeypatch):
    service, _, _, _ = chat_env
    path = Path(__file__).resolve().parents[1] / 'apps/api/migrations/versions/0016_chat_thread_created_index.py'
    spec = importlib.util.spec_from_file_location('thread_created_index', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == '0015_chat_vision'
    with service.engine.begin() as conn:
        conn.execute(sa.text('DROP INDEX ix_chat_threads_owner_created'))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(conn)))
        migration.upgrade()
        indexes = {item['name']: item['column_names'] for item in sa.inspect(conn).get_indexes('chat_threads')}
    assert indexes['ix_chat_threads_owner_created'] == ['account_id', 'created_at', 'id']
