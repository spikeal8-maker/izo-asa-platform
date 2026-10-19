"""Server-owned Graph identities, selection CAS and common lock ordering."""
import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError


def owned_thread(service, conn, raw, thread_id, csrf=None, *, mutation=False):
    account, _ = service._account(conn, raw, csrf, mutation=mutation)
    thread = conn.execute(sa.select(t.threads).where(
        t.threads.c.id == thread_id, t.threads.c.account_id == account["id"]
    ).with_for_update()).mappings().first()
    if thread is None:
        raise ChatError(404, "thread_not_found")
    return account, thread


def locked_request(conn, request_id, account_id=None):
    query = sa.select(t.requests.c.thread_id).where(t.requests.c.id == request_id)
    if account_id is not None:
        query = query.where(t.requests.c.account_id == account_id)
    thread_id = conn.execute(query).scalar_one_or_none()
    if thread_id is None:
        raise ChatError(404, "request_not_found")
    thread_query = sa.select(t.threads.c.id).where(t.threads.c.id == thread_id)
    if account_id is not None:
        thread_query = thread_query.where(t.threads.c.account_id == account_id)
    if conn.execute(thread_query.with_for_update()).first() is None:
        raise ChatError(404, "request_not_found")
    return conn.execute(sa.select(t.requests).where(
        t.requests.c.id == request_id).with_for_update()).mappings().one()


def create_graph(conn, thread_id, now):
    conn.execute(sa.insert(t.branches).values(
        id=thread_id, thread_id=thread_id, created_at=now))
    conn.execute(sa.insert(t.graphs).values(
        thread_id=thread_id, active_branch_id=thread_id, revision=0))


def graph_state(conn, thread_id):
    row = conn.execute(sa.select(t.graphs).where(
        t.graphs.c.thread_id == thread_id)).mappings().first()
    if row is None:
        raise ChatError(409, "graph_unavailable")
    return row


def active_turn(conn, thread_id, turn_id, graph):
    return member_turn(conn, thread_id, turn_id, graph["active_branch_id"])


def owned_branch(conn, thread_id, branch_id):
    row = conn.execute(sa.select(t.branches).where(
        t.branches.c.id == branch_id, t.branches.c.thread_id == thread_id)).mappings().first()
    if row is None:
        raise ChatError(404, "branch_not_found")
    return row


def fenced_graph(conn, thread_id, branch_id=None):
    graph = graph_state(conn, thread_id)
    if branch_id is not None:
        owned_branch(conn, thread_id, branch_id)
        if branch_id != graph["active_branch_id"]:
            raise ChatError(409, "graph_revision_conflict")
    return graph


def member_turn(conn, thread_id, turn_id, branch_id):
    turn = conn.execute(sa.select(t.turns).join(t.branch_turns,
        t.branch_turns.c.turn_id == t.turns.c.id).where(
        t.turns.c.id == turn_id, t.turns.c.thread_id == thread_id,
        t.branch_turns.c.branch_id == branch_id)).mappings().first()
    if turn is None:
        raise ChatError(404, "turn_not_found")
    return turn


def visible_attempts(branch_id):
    return t.attempts.join(t.branch_attempts, sa.and_(
        t.branch_attempts.c.attempt_id == t.attempts.c.id,
        t.branch_attempts.c.branch_id == branch_id))


def member_attempt(conn, thread_id, turn_id, attempt_id, branch_id):
    row = conn.execute(sa.select(t.attempts, t.requests.c.model, t.requests.c.state)
        .select_from(visible_attempts(branch_id).join(t.requests, t.requests.c.id == t.attempts.c.id))
        .where(t.attempts.c.id == attempt_id, t.attempts.c.turn_id == turn_id,
               t.attempts.c.thread_id == thread_id)).mappings().first()
    if row is None:
        raise ChatError(404, "attempt_not_found")
    return row


def check_revision(graph, command):
    if (graph["active_branch_id"] != command.branch_id
            or graph["revision"] != command.expected_revision):
        raise ChatError(409, "graph_revision_conflict")


def advance_revision(conn, thread_id):
    return conn.execute(sa.update(t.graphs).where(t.graphs.c.thread_id == thread_id)
        .values(revision=t.graphs.c.revision + 1).returning(t.graphs.c.revision)).scalar_one()


def add_turn(conn, thread, request_id, user_id, assistant_id):
    graph = graph_state(conn, thread["id"])
    branch_id = graph["active_branch_id"]
    conn.execute(sa.insert(t.turns).values(
        id=user_id, thread_id=thread["id"], branch_id=branch_id,
        user_message_id=user_id, turn_sequence=thread["next_sequence"],
        assistant_display_sequence=thread["next_sequence"] + 1))
    conn.execute(sa.insert(t.branch_turns).values(
        branch_id=branch_id, turn_id=user_id, thread_id=thread["id"]))
    conn.execute(sa.insert(t.attempts).values(
        id=request_id, turn_id=user_id, branch_id=branch_id,
        thread_id=thread["id"], assistant_message_id=assistant_id, ordinal=1))
    conn.execute(sa.insert(t.branch_attempts).values(branch_id=branch_id,
        attempt_id=request_id, turn_id=user_id, thread_id=thread["id"]))
    return conn.execute(sa.select(t.turns).where(t.turns.c.id == user_id)).mappings().one()


def select_completed(conn, request_id, branch_id=None):
    attempt = conn.execute(sa.select(t.attempts).join(
        t.requests, t.requests.c.id == t.attempts.c.id).where(
        t.attempts.c.id == request_id, t.requests.c.state == "completed"
    )).mappings().first()
    if attempt is None:
        raise ChatError(409, "attempt_not_completed")
    graph = graph_state(conn, attempt["thread_id"])
    # Completion is fenced by the request's execution branch. A manual choice
    # may instead select an inherited attempt visible in the current branch.
    branch_id = attempt["branch_id"] if branch_id is None else branch_id
    if graph["active_branch_id"] != branch_id:
        raise ChatError(409, "graph_revision_conflict")
    member_attempt(conn, attempt["thread_id"], attempt["turn_id"], request_id, branch_id)
    existing = conn.execute(sa.select(t.selections.c.attempt_id).where(
        t.selections.c.turn_id == attempt["turn_id"],
        t.selections.c.branch_id == branch_id)).scalar_one_or_none()
    if existing == request_id:
        return
    values = dict(attempt_id=request_id, turn_id=attempt["turn_id"],
                  thread_id=attempt["thread_id"], branch_id=branch_id)
    if existing is None:
        conn.execute(sa.insert(t.selections).values(**values))
    else:
        conn.execute(sa.update(t.selections).where(
            t.selections.c.turn_id == attempt["turn_id"],
            t.selections.c.branch_id == branch_id).values(**values))
    advance_revision(conn, attempt["thread_id"])


def change_selection(service, raw, csrf, thread_id, turn_id, command):
    with service.engine.begin() as conn:
        account, _ = owned_thread(service, conn, raw, thread_id, csrf, mutation=True)
        graph = graph_state(conn, thread_id)
        owned_branch(conn, thread_id, command.branch_id)
        turn = member_turn(conn, thread_id, turn_id, command.branch_id)
        target = member_attempt(conn, thread_id, turn_id, command.attempt_id, command.branch_id)
        check_revision(graph, command)
        select_completed(conn, target["id"], command.branch_id)
        return graph_turn_state(service, conn, account["id"], thread_id, turn)


def graph_turn_state(service, conn, account_id, thread_id, turn):
    from .graph_schemas import GraphTurnState
    from .history_pages import _turn_views
    graph = graph_state(conn, thread_id)
    return GraphTurnState(thread_id=thread_id, active_branch_id=graph["active_branch_id"],
        revision=graph["revision"], turn=_turn_views(service, conn, account_id, thread_id, [turn], graph["active_branch_id"])[0])

def attempt_views(service, conn, thread_id, ids):
    from .graph_schemas import GraphAttemptView
    if not ids:
        return {}
    rows = conn.execute(sa.select(t.attempts.c.id.label("attempt_id"),
        t.attempts.c.turn_id, t.attempts.c.ordinal, t.requests.c.model,
        t.requests.c.state.label("request_state"), t.requests.c.error_code,
        t.requests.c.created_at.label("request_created"),
        t.requests.c.updated_at.label("request_updated"), t.messages).select_from(
        t.attempts.join(t.requests, t.requests.c.id == t.attempts.c.id).join(
            t.messages, t.messages.c.id == t.attempts.c.assistant_message_id)).where(
        t.attempts.c.thread_id == thread_id, t.attempts.c.id.in_(ids))).mappings().all()
    return {row["attempt_id"]: GraphAttemptView(id=row["attempt_id"],
        turn_id=row["turn_id"], request_id=row["attempt_id"], ordinal=row["ordinal"],
        model=row["model"], state=row["request_state"], error_code=row["error_code"],
        message=service._message_view(row), created_at=row["request_created"],
        updated_at=row["request_updated"]) for row in rows}
