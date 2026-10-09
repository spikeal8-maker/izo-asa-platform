"""Account-owned, bounded Chat thread-list pagination."""
import base64
import binascii
import json
import re
from uuid import UUID

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .schemas import THREAD_PAGE_LIMIT, ThreadList, ThreadView


def _boundary(cursor: str | None) -> tuple[int, UUID] | None:
    if cursor is None:
        return None
    try:
        if len(cursor) > 128 or not re.fullmatch(r'[A-Za-z0-9_-]+', cursor):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
        if (set(payload) != {'v', 'updated_at', 'id'} or payload['v'] != 1
                or type(payload['updated_at']) is not int
                or not 0 <= payload['updated_at'] <= 2**63 - 1
                or type(payload['id']) is not str):
            raise ValueError()
        return payload['updated_at'], UUID(payload['id'])
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error):
        raise ChatError(400, 'invalid_thread_cursor') from None


def list_threads(service, raw, cursor: str | None = None) -> ThreadList:
    boundary = _boundary(cursor)
    with service.engine.begin() as conn:
        account, _ = service._account(conn, raw)
        query = sa.select(t.threads).where(t.threads.c.account_id == account['id'])
        if boundary:
            query = query.where(sa.tuple_(t.threads.c.updated_at, t.threads.c.id) < boundary)
        rows = conn.execute(query.order_by(
            t.threads.c.updated_at.desc(), t.threads.c.id.desc()).limit(
            THREAD_PAGE_LIMIT + 1)).mappings().all()
    page = rows[:THREAD_PAGE_LIMIT]
    next_cursor = None
    if len(rows) > THREAD_PAGE_LIMIT:
        last = page[-1]
        payload = {'v': 1, 'updated_at': last['updated_at'], 'id': str(last['id'])}
        next_cursor = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    return ThreadList(threads=[ThreadView(
        id=row['id'], title=row['title'], created_at=row['created_at'],
        updated_at=row['updated_at']) for row in page], next_cursor=next_cursor)
