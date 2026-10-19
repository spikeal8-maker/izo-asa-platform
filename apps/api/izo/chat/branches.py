"""Owned immutable branch forks and metadata selection within the Chat domain."""
from uuid import uuid4

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .graph_context import digest
from .graph_schemas import BRANCH_PAGE_LIMIT, BranchEditView, BranchPage, BranchView
from .graph_selection import advance_revision, check_revision, graph_state, member_attempt
from .graph_selection import member_turn, owned_branch, owned_thread, visible_attempts
from .schemas import RequestCreate


def branch_view(row):
    return BranchView(id=row["id"], parent_branch_id=row["parent_branch_id"],
        fork_from_turn_id=row["fork_from_turn_id"], branch_ordinal=row["branch_ordinal"],
        created_at=row["created_at"])


def branch_page(service, raw, thread_id, before_branch_ordinal=None):
    with service.engine.begin() as conn:
        owned_thread(service, conn, raw, thread_id)
        graph = graph_state(conn, thread_id)
        query = sa.select(t.branches).where(t.branches.c.thread_id == thread_id)
        if before_branch_ordinal is not None:
            query = query.where(t.branches.c.branch_ordinal < before_branch_ordinal)
        rows = conn.execute(query.order_by(t.branches.c.branch_ordinal.desc())
            .limit(BRANCH_PAGE_LIMIT + 1)).mappings().all()
        chosen = rows[:BRANCH_PAGE_LIMIT]
        return BranchPage(thread_id=thread_id, active_branch_id=graph["active_branch_id"],
            active_branch=branch_view(owned_branch(conn, thread_id, graph["active_branch_id"])),
            revision=graph["revision"], branches=[branch_view(row) for row in chosen],
            next_before_branch_ordinal=chosen[-1]["branch_ordinal"] if len(rows) > BRANCH_PAGE_LIMIT else None)


def ensure_idle(conn, thread_id):
    if conn.execute(sa.select(t.requests.c.id).where(t.requests.c.thread_id == thread_id,
        t.requests.c.state.in_(("pending", "streaming"))).limit(1)).first():
        raise ChatError(409, "active_request_exists")


def change_branch(service, raw, csrf, thread_id, command):
    from .graph_projection import project_page
    with service.engine.begin() as conn:
        account, thread = owned_thread(service, conn, raw, thread_id, csrf, mutation=True)
        owned_branch(conn, thread_id, command.branch_id)
        owned_branch(conn, thread_id, command.target_branch_id)
        graph = graph_state(conn, thread_id)
        check_revision(graph, command)
        ensure_idle(conn, thread_id)
        if command.target_branch_id != graph["active_branch_id"]:
            conn.execute(sa.update(t.graphs).where(t.graphs.c.thread_id == thread_id)
                .values(active_branch_id=command.target_branch_id))
            advance_revision(conn, thread_id)
        return project_page(service, conn, account["id"], thread, graph_state(conn, thread_id))


def send_fence(conn, thread_id, command):
    if command.branch_id is not None:
        owned_branch(conn, thread_id, command.branch_id)
        check_revision(graph_state(conn, thread_id), command)
    elif conn.execute(sa.select(t.branches.c.id).where(t.branches.c.thread_id == thread_id,
        t.branches.c.parent_branch_id.is_not(None)).limit(1)).first():
        raise ChatError(409, "branch_selection_required")


def edit_material(service, conn, account_id, thread_id, command, turn_id):
    owned_branch(conn, thread_id, command.branch_id)
    turn = member_turn(conn, thread_id, turn_id, command.branch_id)
    source = member_attempt(conn, thread_id, turn_id, command.source_attempt_id, command.branch_id)
    check_revision(graph_state(conn, thread_id), command)
    selected = conn.execute(sa.select(t.selections.c.attempt_id).where(
        t.selections.c.turn_id == turn_id, t.selections.c.branch_id == command.branch_id)).scalar_one_or_none()
    expected = selected
    if expected is None:
        expected = conn.execute(sa.select(t.attempts.c.id).select_from(
            visible_attempts(command.branch_id).join(t.requests, t.requests.c.id == t.attempts.c.id))
            .where(t.attempts.c.turn_id == turn_id, t.attempts.c.thread_id == thread_id,
                t.requests.c.state.not_in(("pending", "streaming")))
            .order_by(t.attempts.c.ordinal.desc()).limit(1)).scalar_one_or_none()
    if expected != command.source_attempt_id or (selected is not None and source["state"] != "completed"):
        raise ChatError(409, "graph_revision_conflict")
    user = conn.execute(sa.select(t.messages).where(t.messages.c.id == turn["user_message_id"],
        t.messages.c.thread_id == thread_id)).mappings().one()
    # This boundary precedes expiry, remote catalog resolution, rate consumption
    # and durable admission. A rejected UUID remains available for a real edit.
    if command.text == RequestCreate.clean_text(user["content"]):
        raise ChatError(422, "message_unchanged")
    attached = service._attachments_for_messages(conn, account_id, [user["id"]]).get(user["id"], ())
    if not command.text and not attached:
        raise ChatError(422, "invalid_input")
    return RequestCreate(request_id=command.request_id, model=source["model"], text=command.text,
        attachment_ids=[row["asset_id"] for row in attached]), turn


def intent_fingerprint(material_fingerprint, command, turn_id=None, *, edit=False):
    if turn_id is not None:
        return digest({"kind": "edit" if edit else "regenerate", "material": material_fingerprint,
            "turn": str(turn_id), "branch": str(command.branch_id),
            "source_attempt": str(command.source_attempt_id)})
    if command.branch_id is not None:
        return digest({"kind": "send", "material": material_fingerprint, "branch": str(command.branch_id)})
    return material_fingerprint


def edit_receipt(service, conn, row, context=None):
    context = context or conn.execute(sa.select(t.contexts).where(
        t.contexts.c.request_id == row["id"])).mappings().one()
    graph = graph_state(conn, row["thread_id"])
    return BranchEditView(thread_id=row["thread_id"],
        created_branch=branch_view(owned_branch(conn, row["thread_id"], context["branch_id"])),
        turn_id=context["turn_id"], request=service._request_view(row),
        active_branch_id=graph["active_branch_id"], revision=graph["revision"])


def replay_edit(service, conn, account_id, row, context, command, source_turn_id):
    if context["kind"] != "edit":
        raise ChatError(409, "request_conflict")
    user_id = conn.execute(sa.select(t.turns.c.user_message_id).where(
        t.turns.c.id == context["turn_id"])).scalar_one()
    attached = service._attachments_for_messages(conn, account_id, [user_id]).get(user_id, ())
    material = service._request_fingerprint(row["thread_id"], command.text, row["model"],
        row["connection_id"], row["credential_generation"], row["model_revision"],
        [item["asset_id"] for item in attached])
    if row["fingerprint"] != intent_fingerprint(material, command, source_turn_id, edit=True):
        raise ChatError(409, "request_conflict")
    return edit_receipt(service, conn, row, context)


def fork_branch(conn, thread_id, source_turn, command, now):
    child_id = uuid4()
    ordinal = conn.execute(sa.select(sa.func.max(t.branches.c.branch_ordinal)).where(
        t.branches.c.thread_id == thread_id)).scalar_one() + 1
    conn.execute(sa.insert(t.branches).values(id=child_id, thread_id=thread_id,
        parent_branch_id=command.branch_id, fork_from_turn_id=source_turn["id"],
        fork_source_attempt_id=command.source_attempt_id, branch_ordinal=ordinal, created_at=now))
    prefix = sa.select(t.turns.c.id).join(t.branch_turns, t.branch_turns.c.turn_id == t.turns.c.id).where(
        t.branch_turns.c.branch_id == command.branch_id, t.turns.c.thread_id == thread_id,
        t.turns.c.turn_sequence < source_turn["turn_sequence"])
    conn.execute(sa.insert(t.branch_turns).from_select(["branch_id", "turn_id", "thread_id"],
        sa.select(sa.literal(child_id, type_=sa.Uuid), t.turns.c.id, t.turns.c.thread_id)
        .where(t.turns.c.id.in_(prefix))))
    for table, columns in ((t.branch_attempts, ["attempt_id", "turn_id", "thread_id"]),
                           (t.selections, ["turn_id", "thread_id", "attempt_id"])):
        conn.execute(sa.insert(table).from_select(["branch_id", *columns],
            sa.select(sa.literal(child_id, type_=sa.Uuid), *[table.c[name] for name in columns])
            .where(table.c.branch_id == command.branch_id, table.c.turn_id.in_(prefix))))
    conn.execute(sa.update(t.graphs).where(t.graphs.c.thread_id == thread_id)
        .values(active_branch_id=child_id))
    return child_id
