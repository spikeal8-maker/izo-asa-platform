"""Account-owned, sequence-keyed reads of durable Chat messages."""
from uuid import UUID

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .schemas import MESSAGE_PAGE_LIMIT, MessagePage, ThreadDetail


def read_messages(service, raw, thread_id: UUID, before_sequence: int | None):
    with service.engine.begin() as conn:
        account, _ = service._account(conn, raw)
        thread = conn.execute(sa.select(t.threads).where(
            t.threads.c.id == thread_id,
            t.threads.c.account_id == account["id"])).mappings().first()
        if not thread:
            raise ChatError(404, "thread_not_found")
        statement = sa.select(t.messages).where(t.messages.c.thread_id == thread_id)
        if before_sequence is not None:
            statement = statement.where(t.messages.c.sequence < before_sequence)
        rows = conn.execute(statement.order_by(t.messages.c.sequence.desc()).limit(
            MESSAGE_PAGE_LIMIT + 1)).mappings().all()
        has_more = len(rows) > MESSAGE_PAGE_LIMIT
        ordered = list(reversed(rows[:MESSAGE_PAGE_LIMIT]))
        grouped = service._attachments_for_messages(
            conn, account["id"], [row["id"] for row in ordered])
    cursor = ordered[0]["sequence"] if has_more and ordered else None
    messages = [service._message_view(row, grouped.get(row["id"], ()))
                for row in ordered]
    return thread, messages, cursor


def thread_detail(service, raw, thread_id: UUID) -> ThreadDetail:
    thread, messages, cursor = read_messages(service, raw, thread_id, None)
    return ThreadDetail(thread=service._thread_view(thread), messages=messages,
                        next_before_sequence=cursor)


def older_messages(service, raw, thread_id: UUID, before_sequence: int) -> MessagePage:
    _, messages, cursor = read_messages(service, raw, thread_id, before_sequence)
    return MessagePage(messages=messages, next_before_sequence=cursor)
