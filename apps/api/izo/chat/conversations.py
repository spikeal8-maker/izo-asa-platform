"""Durable original messages and Graph attempts share one persistence path."""
from uuid import UUID, uuid4

import sqlalchemy as sa

from . import tables as t
from .attachments import AttachmentMixin
from .branches import fork_branch, intent_fingerprint
from .graph_context import freeze_context
from .graph_selection import add_turn, advance_revision, create_graph, graph_state
from .history_pages import older_messages, thread_detail
from .request_state import RequestStateMixin
from .schemas import MessageView, RequestView, ThreadDetail, ThreadList, ThreadView
from .thread_pages import list_threads, thread_view
from .thread_titles import rename_thread


class ConversationMixin(AttachmentMixin, RequestStateMixin):
    def create_thread(self, raw, csrf, title: str | None) -> ThreadView:
        now, thread_id = self.now(), uuid4()
        safe = (title or "Новый чат").strip()[:120] or "Новый чат"
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw, csrf, mutation=True)
            conn.execute(sa.insert(t.threads).values(id=thread_id,
                account_id=account["id"], title=safe, next_sequence=1,
                created_at=now, updated_at=now))
            create_graph(conn, thread_id, now)
        return ThreadView(id=thread_id, title=safe, created_at=now, updated_at=now)

    def rename_thread(self, raw, csrf, thread_id: UUID, title: str) -> ThreadView:
        return rename_thread(self, raw, csrf, thread_id, title)

    @staticmethod
    def _thread_view(row) -> ThreadView:
        return thread_view(row)

    def list_threads(self, raw, cursor: str | None = None) -> ThreadList:
        return list_threads(self, raw, cursor)

    @classmethod
    def _message_view(cls, row, attachment_rows=()) -> MessageView:
        return MessageView(id=row["id"], request_id=row["request_id"], role=row["role"],
            sequence=row["sequence"], content=row["content"], state=row["state"],
            attachments=[cls._attachment_view(item) for item in attachment_rows],
            created_at=row["created_at"], updated_at=row["updated_at"])

    def thread_detail(self, raw, thread_id: UUID) -> ThreadDetail:
        return thread_detail(self, raw, thread_id)

    def older_messages(self, raw, thread_id: UUID, before_sequence: int):
        return older_messages(self, raw, thread_id, before_sequence)

    def create_request(self, raw, csrf, thread_id: UUID, command) -> RequestView:
        from .graph_requests import admit_request
        return admit_request(self, raw, csrf, thread_id, command)


def persist_request(service, conn, account_id, thread, command, material, turn, admission, *, edit=False):
    connection, revision, vision, assets = admission
    fingerprint = service._request_fingerprint(thread["id"], material.text, material.model,
        connection["id"], connection["generation"], revision, material.attachment_ids)
    fingerprint = intent_fingerprint(fingerprint, command, turn["id"] if turn else None, edit=edit)
    now, request_id, assistant_id = service.now(), material.request_id, uuid4()
    sequence = thread["next_sequence"]
    if edit:
        fork_branch(conn, thread["id"], turn, command, now)
    conn.execute(sa.insert(t.requests).values(
        id=request_id, thread_id=thread["id"], account_id=account_id,
        fingerprint=fingerprint, model=material.model, model_revision=revision,
        connection_id=connection["id"], credential_generation=connection["generation"],
        vision_admitted=vision, state="pending", created_at=now, updated_at=now,
        deadline_at=now + service.policy.request_deadline_seconds))
    regenerate = turn is not None and not edit
    if not regenerate:
        user_id = uuid4()
        conn.execute(sa.insert(t.messages).values(id=user_id, thread_id=thread["id"],
            request_id=request_id, role="user", sequence=sequence, part_version=1,
            content=material.text, state="complete", created_at=now, updated_at=now))
        service._insert_attachments(conn, account_id, request_id, user_id, assets, now)
    conn.execute(sa.insert(t.messages).values(id=assistant_id, thread_id=thread["id"],
        request_id=request_id, role="assistant", sequence=sequence if regenerate else sequence + 1,
        part_version=1, content="", state="partial", created_at=now, updated_at=now))
    if regenerate:
        ordinal = conn.execute(sa.select(sa.func.max(t.attempts.c.ordinal)).where(
            t.attempts.c.turn_id == turn["id"])).scalar_one() + 1
        branch_id = graph_state(conn, thread["id"])["active_branch_id"]
        conn.execute(sa.insert(t.attempts).values(id=request_id, turn_id=turn["id"],
            thread_id=thread["id"], branch_id=branch_id, ordinal=ordinal,
            assistant_message_id=assistant_id, source_attempt_id=command.source_attempt_id))
        conn.execute(sa.insert(t.branch_attempts).values(branch_id=branch_id,
            attempt_id=request_id, turn_id=turn["id"], thread_id=thread["id"]))
    else:
        turn = add_turn(conn, thread, request_id, user_id, assistant_id)
    title = thread["title"]
    if not regenerate and sequence == 1 and title == "Новый чат" and not thread["title_is_manual"]:
        title = material.text.replace("\n", " ").strip()[:72] or "Изображение"
    conn.execute(sa.update(t.threads).where(t.threads.c.id == thread["id"]).values(
        next_sequence=sequence + (1 if regenerate else 2), title=title, updated_at=now))
    advance_revision(conn, thread["id"])
    row = conn.execute(sa.select(t.requests).where(t.requests.c.id == request_id)).mappings().one()
    freeze_context(service, conn, row, turn, "edit" if edit else "regenerate" if regenerate else "send")
    return row, turn["id"] if regenerate else None
