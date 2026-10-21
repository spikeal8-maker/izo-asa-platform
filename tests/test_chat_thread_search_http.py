"""Existing HTTP list gains owned full-history search with safe failure bodies."""
from threading import BoundedSemaphore

import pytest
import sqlalchemy as sa

from izo.chat import thread_pages
from test_chat_http import http_env, signup

PATH = "/api/v1/chat/threads"


def test_http_search_deep_history_pages_and_account_fence(http_env):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    ids = []
    for _ in range(151):
        response = client.post(PATH, json={"title": "Common"})
        assert response.status_code == 201
        ids.append(response.json()["id"])
    oldest = min(ids)
    assert client.patch(f"{PATH}/{oldest}", json={"title": "Needle Common"}).status_code == 200
    ordinary = client.get(PATH).json()
    later = client.get(PATH, params={"cursor": ordinary["next_cursor"]}).json()
    assert oldest not in {row["id"] for row in ordinary["threads"] + later["threads"]}
    result = client.get(PATH, params={"q": " needle "})
    assert result.status_code == 200
    assert set(result.json()) == {"threads", "next_cursor"}
    assert [row["id"] for row in result.json()["threads"]] == [oldest]
    assert set(result.json()["threads"][0]) == {"id", "title", "created_at", "updated_at"}
    first = client.get(PATH, params={"q": "COMMON"}).json()
    rows, cursor = first["threads"], first["next_cursor"]
    while cursor:
        page = client.get(PATH, params={"q": " common ", "cursor": cursor})
        assert page.status_code == 200
        rows += page.json()["threads"]
        cursor = page.json()["next_cursor"]
    assert [row["id"] for row in rows] == sorted(ids, reverse=True)
    assert len(rows) == 151
    assert client.get(PATH, params={"q": " \ufeff\t"}).json() == ordinary
    for params in ({"q": "other", "cursor": first["next_cursor"]},
                   {"cursor": first["next_cursor"]},
                   {"q": "common", "cursor": ordinary["next_cursor"]}):
        rejected = client.get(PATH, params=params)
        assert rejected.status_code == 400
        assert rejected.json() == {"error": {"code": "invalid_thread_cursor"}}
    client.cookies.clear()
    assert client.get(PATH, params={"q": "common"}).status_code == 401
    signup(auth, client, "bob@example.invalid")
    assert client.get(PATH, params={"q": "common"}).json() == {"threads": [], "next_cursor": None}
    foreign = client.get(PATH, params={"q": "common", "cursor": first["next_cursor"]})
    assert foreign.status_code == 400
    assert foreign.json() == {"error": {"code": "invalid_thread_cursor"}}


@pytest.mark.parametrize(("query", "status"), [
    ("x" * 256, 200), ("😀" * 256, 200), ("x" * 257, 422),
    ("😀" * 257, 422), ("İ" * 121, 200), ("private\0query", 400),
])
def test_http_query_unicode_codepoint_bounds_and_safe_errors(http_env, query, status):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    response = client.get(PATH, params={"q": query})
    assert response.status_code == status
    if status == 200:
        assert response.json() == {"threads": [], "next_cursor": None}
    else:
        assert response.json() == {"error": {"code": "invalid_input"}}
        assert "private" not in response.text


def test_http_literal_unicode_queries_and_rename_membership(http_env):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    thread = client.post(PATH, json={"title": "ΟΣ 100%_\\"}).json()
    for query in ("\ufeff ΟΣ ", "%", "_", "\\"):
        response = client.get(PATH, params={"q": query})
        assert response.status_code == 200
        assert response.json()["threads"] == [thread]
    assert client.get(PATH, params={"q": "οσ"}).json()["threads"] == []
    renamed = client.patch(f"{PATH}/{thread['id']}", json={"title": "İstanbul"}).json()
    assert client.get(PATH, params={"q": "%"}).json()["threads"] == []
    assert client.get(PATH, params={"q": "i\u0307"}).json()["threads"] == [renamed]


@pytest.mark.parametrize("cause", ["capacity", "pool"])
def test_http_search_unavailable_has_no_partial_page_or_private_details(http_env, monkeypatch, cause):
    auth, service, client = http_env
    signup(auth, client, "alice@example.invalid")
    guard = BoundedSemaphore(2)
    monkeypatch.setattr(thread_pages, "_SEARCH_PERMITS", guard)
    if cause == "capacity":
        guard.acquire(); guard.acquire()
    else:
        def failure():
            raise sa.exc.TimeoutError("private connection details")
        monkeypatch.setattr(service.engine, "begin", failure)
    try:
        response = client.get(PATH, params={"q": "private query"})
        assert response.status_code == 503
        assert response.json() == {"error": {"code": "search_unavailable"}}
        assert "private" not in response.text
    finally:
        if cause == "capacity":
            guard.release(); guard.release()
