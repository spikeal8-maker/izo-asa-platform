"""Account-owned, bounded Chat thread-list pagination."""
import base64
import binascii
import json
import re
from threading import BoundedSemaphore
from uuid import UUID

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .schemas import THREAD_PAGE_LIMIT, ThreadList, ThreadView
from .thread_title_search_v1 import query_key, search_boundary, search_cursor

_SEARCH_PERMITS = BoundedSemaphore(2)


def _boundary(cursor: str | None) -> tuple[int, UUID] | None:
    if cursor is None:
        return None
    try:
        if len(cursor) > 128 or not re.fullmatch(r'[A-Za-z0-9_-]+', cursor):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
        if (set(payload) != {'v', 'created_at', 'id'} or payload['v'] != 1
                or type(payload['created_at']) is not int
                or not 0 <= payload['created_at'] <= 2**63 - 1
                or type(payload['id']) is not str):
            raise ValueError()
        return payload['created_at'], UUID(payload['id'])
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error):
        raise ChatError(400, 'invalid_thread_cursor') from None


def thread_view(row) -> ThreadView:
    return ThreadView(
        id=row['id'], title=row['title'], created_at=row['created_at'],
        updated_at=row['updated_at'])


def list_threads(service, raw, cursor: str | None = None, q: str = "") -> ThreadList:
    if not isinstance(q, str) or len(q) > 256:
        raise ChatError(422, "invalid_input")
    try:
        key = query_key(q)
    except ValueError:
        raise ChatError(400, "invalid_input") from None
    if not key:
        return _page(service, raw, cursor, key)
    if not _SEARCH_PERMITS.acquire(blocking=False):
        raise ChatError(503, "search_unavailable")
    try:
        return _page(service, raw, cursor, key)
    except sa.exc.TimeoutError:
        raise ChatError(503, "search_unavailable") from None
    except sa.exc.DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) in {"57014", "55P03"}:
            raise ChatError(503, "search_unavailable") from None
        raise
    finally:
        _SEARCH_PERMITS.release()


def _page(service, raw, cursor, key) -> ThreadList:
    boundary = _boundary(cursor) if not key else None
    with service.engine.begin() as conn:
        account, _ = service._account(conn, raw)
        if key:
            try:
                boundary = search_boundary(cursor, account["id"], key)
            except ValueError:
                raise ChatError(400, "invalid_thread_cursor") from None
            if len(key) > 240:
                return ThreadList(threads=[], next_cursor=None)
        query = sa.select(t.threads).where(t.threads.c.account_id == account['id'])
        if boundary:
            query = query.where(sa.tuple_(t.threads.c.created_at, t.threads.c.id) < boundary)
        if key:
            match = sa.func.strpos if conn.dialect.name == "postgresql" else sa.func.instr
            query = query.where(match(t.threads.c.title_search_key, key) > 0)
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql("SET LOCAL statement_timeout = '1000ms'")
        rows = conn.execute(query.order_by(
            t.threads.c.created_at.desc(), t.threads.c.id.desc()).limit(
            THREAD_PAGE_LIMIT + 1)).mappings().all()
    page = rows[:THREAD_PAGE_LIMIT]
    next_cursor = None
    if len(rows) > THREAD_PAGE_LIMIT:
        last = page[-1]
        if key:
            next_cursor = search_cursor(account["id"], key, last)
        else:
            payload = {'v': 1, 'created_at': last['created_at'], 'id': str(last['id'])}
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    return ThreadList(threads=[thread_view(row) for row in page], next_cursor=next_cursor)
