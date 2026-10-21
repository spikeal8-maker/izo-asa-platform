"""Owned thread-title mutation serialized with first-message admission."""
from uuid import UUID

import sqlalchemy as sa
from pydantic import ValidationError

from . import tables as t
from .credentials import ChatError
from .schemas import ThreadRename, ThreadView
from .thread_pages import thread_view
from .thread_title_search_v1 import title_key


def rename_thread(service, raw, csrf, thread_id: UUID, title: str) -> ThreadView:
    with service.engine.begin() as conn:
        account, _ = service._account(conn, raw, csrf, mutation=True)
        row = conn.execute(sa.select(t.threads).where(
            t.threads.c.id == thread_id,
            t.threads.c.account_id == account["id"]
        ).with_for_update()).mappings().first()
        if row is None:
            raise ChatError(404, "thread_not_found")
        try:
            safe = ThreadRename(title=title).title
        except ValidationError as exc:
            raise ChatError(422, "invalid_input") from exc
        if row["title_is_manual"] and row["title"] == safe:
            return thread_view(row)
        updated = conn.execute(sa.update(t.threads).where(
            t.threads.c.id == thread_id,
            t.threads.c.account_id == account["id"]
        ).values(title=safe, title_search_key=title_key(safe), title_is_manual=True,
                 updated_at=max(row["updated_at"], service.now()))
          .returning(t.threads)).mappings().one()
        return thread_view(updated)
