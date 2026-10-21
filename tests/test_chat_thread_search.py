"""Whole-history literal search, cursor binding and bounded admission."""
import base64
import json
from threading import BoundedSemaphore
from uuid import UUID

import pytest
import sqlalchemy as sa

from izo.accounts.security import AuthError
from izo.chat import conversations, tables as t, thread_pages
from izo.chat.credentials import ChatError
from izo.chat import thread_title_search_v1 as matcher
from test_chat import chat_env, connect_key, new_thread, request


def create(service, owner, title):
    return service.create_thread(owner.bearer, owner.view.csrf_token, title)


def complete_history(environment):
    service, alice, bob, clock = environment
    ids = [create(service, alice, "Common title").id for _ in range(151)]
    foreign = create(service, bob, "Needle Common").id
    oldest = min(ids)
    service.rename_thread(alice.bearer, alice.view.csrf_token, oldest, "Needle Common")
    ordinary = service.list_threads(alice.bearer)
    second = service.list_threads(alice.bearer, ordinary.next_cursor)
    assert oldest not in {row.id for row in ordinary.threads + second.threads}
    found = service.list_threads(alice.bearer, q=" needle ")
    assert [row.id for row in found.threads] == [oldest] and found.next_cursor is None
    cursor, seen, new = None, [], None
    while True:
        page = service.list_threads(alice.bearer, cursor, "\ufeffCOMMON ")
        seen += [row.id for row in page.threads]
        assert len(page.threads) <= 50
        if not page.next_cursor:
            break
        assert len(page.next_cursor) <= 256 and page.next_cursor.isascii()
        cursor = page.next_cursor
        if new is None:
            clock[0] += 1
            new = create(service, alice, "Common newer").id
            service.rename_thread(alice.bearer, alice.view.csrf_token, oldest, "Common renamed")
    assert seen == sorted(ids, reverse=True)
    assert len(seen) == len(set(seen)) == 151 and foreign not in seen and new not in seen
    assert service.list_threads(alice.bearer, q="common").threads[0].id == new
    assert service.list_threads(alice.bearer, q="no such title").threads == []
    assert [row.id for row in service.list_threads(bob.bearer, q="common").threads] == [foreign]


def test_complete_history_and_ties(chat_env):
    complete_history(chat_env)


def unicode_matches(environment):
    service, alice, _, _ = environment
    titles = ["ΟΣ", "ΟΣΑ", "İstanbul", "Straße", "CAFÉ", "Cafe\u0301",
              "\u0085X\u0085", "100%_\\note", "😀 Supplementary"]
    ids = {}
    for title in titles:
        thread = create(service, alice, title)
        service.rename_thread(alice.bearer, alice.view.csrf_token, thread.id, title)
        ids[title] = thread.id
    cases = [(" \ufeffΟΣ\u3000", ["ΟΣ"]), ("οσ", ["ΟΣΑ"]), ("İ", ["İstanbul"]),
             ("i\u0307", ["İstanbul"]), ("ß", ["Straße"]), ("ss", []),
             ("é", ["CAFÉ"]), ("e\u0301", ["Cafe\u0301"]), ("\u0085", ["\u0085X\u0085"]),
             ("%", ["100%_\\note"]), ("_", ["100%_\\note"]), ("\\", ["100%_\\note"]),
             ("😀", ["😀 Supplementary"])]
    for query, expected in cases:
        result = service.list_threads(alice.bearer, q=query)
        assert {row.id for row in result.threads} == {ids[title] for title in expected}, repr(query)
    assert service.list_threads(alice.bearer, q=" \ufeff\t") == service.list_threads(alice.bearer)


def test_declared_unicode_and_literal_matching(chat_env):
    unicode_matches(chat_env)


def test_cursor_binding_and_strict_shape(chat_env):
    service, alice, bob, _ = chat_env
    for _ in range(51):
        create(service, alice, "Match")
    first = service.list_threads(alice.bearer, q="match")
    cursor = first.next_cursor
    assert len(service.list_threads(alice.bearer, cursor, " MATCH ").threads) == 1
    legacy = service.list_threads(alice.bearer).next_cursor
    bad = [(alice.bearer, cursor, "changed"), (bob.bearer, cursor, "match"),
           (alice.bearer, cursor, ""), (alice.bearer, legacy, "match"),
           (alice.bearer, cursor, "x" * 241)]
    payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    for field, value in [("v", True), ("m", 2), ("m", True), ("t", True),
                         ("t", -1), ("t", 2**63), ("i", 1), ("q", "wrong")]:
        changed = {**payload, field: value}
        encoded = base64.urlsafe_b64encode(json.dumps(changed).encode()).decode().rstrip("=")
        bad.append((alice.bearer, encoded, "match"))
    bad += [(alice.bearer, value, "match") for value in ("", "?", "a" * 257, "W10", "bnVsbA")]
    for owner, value, query in bad:
        with pytest.raises(ChatError, match="invalid_thread_cursor") as error:
            service.list_threads(owner, value, query)
        assert error.value.status == 400
    assert service.list_threads(alice.bearer, legacy, " \ufeff") == service.list_threads(alice.bearer, legacy)
    maximum = matcher.search_cursor(alice.view.account.id, "İ" * 256,
        {"created_at": 2**63 - 1, "id": UUID(int=2**128 - 1)})
    assert len(maximum) <= 256


def test_query_bounds_before_database_and_runtime_pin(chat_env, monkeypatch):
    service, alice, _, _ = chat_env
    for query in ("x" * 256, "😀" * 256, "İ" * 121):
        result = service.list_threads(alice.bearer, q=query)
        assert result.threads == [] and result.next_cursor is None
    def forbidden():
        raise AssertionError("invalid query reached database")
    monkeypatch.setattr(service.engine, "begin", forbidden)
    for query, status in [("x" * 257, 422), ("secret\0query", 400), ("\ud800", 400)]:
        with pytest.raises(ChatError, match="invalid_input") as error:
            service.list_threads(alice.bearer, q=query)
        assert error.value.status == status
    monkeypatch.setattr(matcher.unicodedata, "unidata_version", "16.0.0")
    with pytest.raises(RuntimeError, match="Unicode 15.1"):
        matcher.title_key("Title")
    with pytest.raises(RuntimeError, match="Unicode 15.1"):
        service.list_threads(alice.bearer, q="Title")


def title_writes(environment):
    service, alice, _, _ = environment
    connect_key(service, alice)
    thread = new_thread(service, alice)
    admitted = request(service, alice, thread.id, "ΟΣ first title")
    assert service.list_threads(alice.bearer, q="ος first").threads[0].id == thread.id
    service.rename_thread(alice.bearer, alice.view.csrf_token, thread.id, "İ manual")
    assert service.list_threads(alice.bearer, q="ος first").threads == []
    assert service.list_threads(alice.bearer, q="i\u0307 manual").threads[0].id == thread.id
    assert request(service, alice, thread.id, "ΟΣ first title", request_id=admitted.id) == admitted
    with service.engine.connect() as conn:
        row = conn.execute(sa.select(t.threads).where(t.threads.c.id == thread.id)).mappings().one()
    assert row["title_search_key"] == "i\u0307 manual" and row["title_is_manual"]
    assert "title_search_key" not in service.list_threads(alice.bearer, q="manual").model_dump_json()


def test_atomic_title_writers_and_replay(chat_env):
    title_writes(chat_env)


def test_failed_first_admission_rolls_back_key_with_title(chat_env, monkeypatch):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = new_thread(service, alice)
    def fail(*_):
        raise ChatError(422, "injected_context_failure")
    monkeypatch.setattr(conversations, "freeze_context", fail)
    with pytest.raises(ChatError, match="injected_context_failure"):
        request(service, alice, thread.id, "Failed title")
    assert service.list_threads(alice.bearer, q="failed").threads == []
    assert service.list_threads(alice.bearer, q="новый чат").threads == [thread]


def assert_permits_available():
    guard = thread_pages._SEARCH_PERMITS
    assert guard.acquire(blocking=False)
    try:
        assert guard.acquire(blocking=False)
        try:
            assert not guard.acquire(blocking=False)
        finally:
            guard.release()
    finally:
        guard.release()


def test_capacity_rejects_before_pool_and_ordinary_list_bypasses(chat_env, monkeypatch):
    service, alice, _, _ = chat_env
    guard = BoundedSemaphore(2)
    monkeypatch.setattr(thread_pages, "_SEARCH_PERMITS", guard)
    guard.acquire(); guard.acquire()
    try:
        with pytest.MonkeyPatch.context() as patch:
            def forbidden():
                raise AssertionError("refused search checked out a connection")
            patch.setattr(service.engine, "begin", forbidden)
            with pytest.raises(ChatError, match="search_unavailable") as error:
                service.list_threads(alice.bearer, q="query")
            assert error.value.status == 503
        assert service.list_threads(alice.bearer, q=" \ufeff").threads == []
    finally:
        guard.release(); guard.release()
    service.list_threads(alice.bearer, q="query")
    with pytest.raises(AuthError):
        service.list_threads(None, q="query")
    with pytest.raises(ChatError, match="invalid_thread_cursor"):
        service.list_threads(alice.bearer, "bad", "query")
    assert_permits_available()


@pytest.mark.parametrize("kind", ["pool", "57014", "55P03", "23505", "unexpected"])
def test_failure_mapping_is_narrow_and_always_releases(chat_env, monkeypatch, kind):
    service, alice, _, _ = chat_env
    if kind == "pool":
        failure = sa.exc.TimeoutError("private pool details")
    elif kind == "unexpected":
        failure = RuntimeError("unrelated fault")
    else:
        original = Exception("private driver details")
        original.sqlstate = kind
        failure = sa.exc.DBAPIError("private SQL", {}, original)
    def failed_checkout():
        raise failure
    monkeypatch.setattr(service.engine, "begin", failed_checkout)
    expected = ChatError if kind in {"pool", "57014", "55P03"} else type(failure)
    with pytest.raises(expected) as error:
        service.list_threads(alice.bearer, q="query")
    if expected is ChatError:
        assert (error.value.status, error.value.code) == (503, "search_unavailable")
    else:
        assert error.value is failure
    assert_permits_available()
