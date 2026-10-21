"""Standalone isolated PostgreSQL acceptance; every named case runs or fails."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Event, Lock
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from izo.accounts import tables as accounts
from izo.chat import tables as t, thread_pages
from izo.chat.credentials import ChatError
from test_chat import connect_key, new_thread, request
from test_chat_graph_migration import pg_environment
import test_chat_thread_search as domain
from test_chat_thread_search_migration import retained_backfill


def timeout_rollback(environment):
    service, alice, _, _ = environment
    domain.create(service, alice, "Timeout recovery")
    engine = service.engine
    observed = []

    def inspect_timeout(conn, cursor, statement, parameters, context, many):
        if "strpos(" in statement:
            observed.append(conn.exec_driver_sql("SHOW statement_timeout").scalar_one())

    sa.event.listen(engine, "before_cursor_execute", inspect_timeout)
    try:
        with engine.connect() as reused:
            baseline = reused.exec_driver_sql("SHOW statement_timeout").scalar_one()
            reused.commit()

            @contextmanager
            def fixed_begin():
                with reused.begin():
                    yield reused

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(service, "engine", SimpleNamespace(begin=fixed_begin))
                with engine.begin() as blocker:
                    blocker.exec_driver_sql("LOCK TABLE chat_threads IN ACCESS EXCLUSIVE MODE")
                    with pytest.raises(ChatError, match="search_unavailable") as error:
                        service.list_threads(alice.bearer, q="timeout")
                    assert error.value.status == 503
                    assert not reused.in_transaction()
                    # Only the thread table is still blocked; authorization locks must be gone.
                    with engine.begin() as observer:
                        assert observer.execute(sa.select(accounts.accounts.c.id).where(
                            accounts.accounts.c.id == alice.view.account.id)
                            .with_for_update(nowait=True)).scalar_one() == alice.view.account.id
                        assert observer.execute(sa.select(accounts.sessions.c.id).where(
                            accounts.sessions.c.account_id == alice.view.account.id)
                            .with_for_update(nowait=True)).first() is not None
                    assert reused.exec_driver_sql("SHOW statement_timeout").scalar_one() == baseline
                    reused.commit()
                result = service.list_threads(alice.bearer, q="timeout")
                assert len(result.threads) == 1 and result.next_cursor is None
                assert reused.exec_driver_sql("SHOW statement_timeout").scalar_one() == baseline
                reused.commit()
            assert baseline == "15s"  # Actual isolated fixture, not the production 5s setting.
    finally:
        sa.event.remove(engine, "before_cursor_execute", inspect_timeout)
    assert observed == ["1s", "1s"]
    domain.assert_permits_available()


def concurrent_capacity(environment):
    service, alice, bob, _ = environment
    ready, release, lock = Event(), Event(), Lock()
    entered, checkouts = [], []

    def hold(conn, cursor, statement, parameters, context, many):
        if "strpos(" in statement:
            with lock:
                entered.append(True)
                if len(entered) == 2:
                    ready.set()
            assert release.wait(10), "search test barrier timed out"

    def checkout(*_):
        checkouts.append(True)

    sa.event.listen(service.engine, "before_cursor_execute", hold)
    sa.event.listen(service.engine, "checkout", checkout)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            jobs = [workers.submit(service.list_threads, owner.bearer, q="common") for owner in (alice, bob)]
            try:
                assert ready.wait(5), "two authenticated searches did not reach SELECT"
                before = len(checkouts)
                with pytest.raises(ChatError, match="search_unavailable") as error:
                    service.list_threads(alice.bearer, q="common")
                assert error.value.status == 503 and len(checkouts) == before
            finally:
                release.set()
            assert all(job.result(timeout=10).threads == [] for job in jobs)
    finally:
        release.set()
        sa.event.remove(service.engine, "before_cursor_execute", hold)
        sa.event.remove(service.engine, "checkout", checkout)
    domain.assert_permits_available()


def exhausted_pool(environment):
    service, alice, _, _ = environment
    single = sa.create_engine(service.engine.url, pool_size=1, max_overflow=0,
        pool_timeout=0.05, hide_parameters=True, connect_args={"options":
        f"-c search_path={service._graph_pg_label} -c statement_timeout=15000 -c lock_timeout=12000"})
    selected = []

    @sa.event.listens_for(single, "before_cursor_execute")
    def observe(conn, cursor, statement, parameters, context, many):
        if "strpos(" in statement:
            selected.append(True)

    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(service, "engine", single)
            with single.connect():
                with pytest.raises(ChatError, match="search_unavailable") as error:
                    service.list_threads(alice.bearer, q="common")
                assert error.value.status == 503 and selected == []
                domain.assert_permits_available()
            assert service.list_threads(alice.bearer, q="common").threads == []
            assert selected == [True]
    finally:
        single.dispose()
    domain.assert_permits_available()


def concurrent_titles(environment):
    service, alice, _, clock = environment
    ids = [domain.create(service, alice, "Common").id for _ in range(101)]
    first = service.list_threads(alice.bearer, q="common")
    clock[0] += 1
    barrier = Barrier(3)

    def create():
        barrier.wait(5)
        return domain.create(service, alice, "Common new")

    def rename():
        barrier.wait(5)
        return service.rename_thread(alice.bearer, alice.view.csrf_token, min(ids), "Common renamed")

    with ThreadPoolExecutor(max_workers=2) as workers:
        new, renamed = workers.submit(create), workers.submit(rename)
        barrier.wait(5)
        seen, cursor = [row.id for row in first.threads], first.next_cursor
        while cursor:
            page = service.list_threads(alice.bearer, cursor, "common")
            seen += [row.id for row in page.threads]
            cursor = page.next_cursor
        created, updated = new.result(timeout=10), renamed.result(timeout=10)
    assert seen == sorted(ids, reverse=True) and len(set(seen)) == 101
    assert service.list_threads(alice.bearer, q="common").threads[0].id == created.id
    assert service.list_threads(alice.bearer, q="renamed").threads == [updated]
    connect_key(service, alice)
    thread = new_thread(service, alice)
    barrier = Barrier(2)

    def first_send():
        barrier.wait(5)
        return request(service, alice, thread.id, "Automatic first")

    def manual_title():
        barrier.wait(5)
        return service.rename_thread(alice.bearer, alice.view.csrf_token, thread.id, "Manual choice")

    with ThreadPoolExecutor(max_workers=2) as workers:
        sent, chosen = workers.submit(first_send), workers.submit(manual_title)
        sent.result(timeout=10); chosen.result(timeout=10)
    assert service.list_threads(alice.bearer, q="manual choice").threads[0].id == thread.id
    assert service.list_threads(alice.bearer, q="automatic first").threads == []
    with service.engine.connect() as conn:
        rows = conn.execute(sa.select(t.threads.c.title, t.threads.c.title_search_key)).all()
    assert all(key == title.lower() for title, key in rows)


def run_postgres():
    cases = [
        ("whole_history_151_and_owner_keyset", domain.complete_history),
        ("literal_unicode_postgresql", domain.unicode_matches),
        ("atomic_title_writers_and_replay", domain.title_writes),
        ("forward_migration_504_and_graph_retention", retained_backfill),
        ("timeout_rollback_auth_locks_and_restore", timeout_rollback),
        ("two_searches_and_precheckout_refusal", concurrent_capacity),
        ("exhausted_pool_and_permit_recovery", exhausted_pool),
        ("concurrent_create_rename_first_admission", concurrent_titles),
    ]
    assert cases and len({name for name, _ in cases}) == len(cases)
    for name, check in cases:
        with pg_environment() as environment:
            check(environment)
        print("POSTGRES_SEARCH_PASS " + name, flush=True)
    print(f"POSTGRES_SEARCH_PASS cases={len(cases)}", flush=True)


if __name__ == "__main__":
    run_postgres()
