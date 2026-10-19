"""Branch-scoped Graph reads under the owned Thread snapshot lock."""
import sqlalchemy as sa

from . import tables as t
from .graph_selection import attempt_views as _attempt_views
from .graph_selection import active_turn, fenced_graph, graph_state, owned_thread, visible_attempts

def _turn_views(service, conn, account_id, thread_id, turns, branch_id):
    from .graph_schemas import GraphTurnView
    if not turns:
        return []
    turn_ids = [turn["id"] for turn in turns]
    selected_attempt = t.attempts.alias("selected_attempt")
    selected = conn.execute(sa.select(t.selections.c.turn_id,
        t.selections.c.attempt_id).where(t.selections.c.turn_id.in_(turn_ids),
        t.selections.c.branch_id == branch_id)).all()
    selected_ids = dict(selected)
    complete = t.requests.c.state == "completed"
    selected_ordinal = selected_attempt.c.ordinal
    # Aggregate counts/navigation inside SQL. A page never materializes every
    # historical variant or performs one query per turn.
    rows = conn.execute(sa.select(t.attempts.c.turn_id,
        sa.func.max(t.attempts.c.ordinal).label("latest"),
        sa.func.sum(sa.case((complete, 1), else_=0)).label("completed_count"),
        sa.func.sum(sa.case((sa.and_(complete, t.attempts.c.ordinal <= selected_ordinal), 1),
                           else_=0)).label("position"),
        sa.func.max(sa.case((sa.and_(complete, t.attempts.c.ordinal < selected_ordinal),
                            t.attempts.c.ordinal))).label("previous"),
        sa.func.min(sa.case((sa.and_(complete, t.attempts.c.ordinal > selected_ordinal),
                            t.attempts.c.ordinal))).label("next")
    ).select_from(visible_attempts(branch_id).join(t.requests, t.requests.c.id == t.attempts.c.id)
        .outerjoin(t.selections, sa.and_(t.selections.c.turn_id == t.attempts.c.turn_id,
                                       t.selections.c.branch_id == branch_id))
        .outerjoin(selected_attempt, selected_attempt.c.id == t.selections.c.attempt_id))
        .where(t.attempts.c.turn_id.in_(turn_ids), t.attempts.c.thread_id == thread_id).group_by(t.attempts.c.turn_id)).mappings().all()
    stats = {row["turn_id"]: row for row in rows}
    ordinals = [(row["turn_id"], row[key]) for row in rows
                for key in ("latest", "previous", "next") if row[key] is not None]
    neighbors = conn.execute(sa.select(t.attempts.c.turn_id, t.attempts.c.ordinal,
        t.attempts.c.id).select_from(visible_attempts(branch_id)).where(sa.tuple_(t.attempts.c.turn_id, t.attempts.c.ordinal)
        .in_(ordinals))).all() if ordinals else []
    by_ordinal = {(row.turn_id, row.ordinal): row.id for row in neighbors}
    latest_ids = {turn_id: by_ordinal[(turn_id, row["latest"])] for turn_id, row in stats.items()}
    views = _attempt_views(service, conn, thread_id, set(selected_ids.values()) | set(latest_ids.values()))
    user_ids = [turn["user_message_id"] for turn in turns]
    users = {row["id"]: row for row in conn.execute(sa.select(t.messages).where(
        t.messages.c.thread_id == thread_id, t.messages.c.id.in_(user_ids))).mappings()}
    attached = service._attachments_for_messages(conn, account_id, user_ids)
    output = []
    for turn in turns:
        identity = turn["id"]
        selected_id = selected_ids.get(identity)
        row = stats.get(identity, {})
        user_id = turn["user_message_id"]
        output.append(GraphTurnView(id=identity, turn_sequence=turn["turn_sequence"],
            assistant_display_sequence=turn["assistant_display_sequence"],
            user_message=service._message_view(users[user_id], attached.get(user_id, ())),
            selected_attempt_id=selected_id, selected_attempt=views.get(selected_id),
            latest_attempt=views.get(latest_ids.get(identity)),
            completed_count=row.get("completed_count", 0),
            selected_completed_position=row.get("position") if selected_id else None,
            previous_completed_attempt_id=by_ordinal.get((identity, row.get("previous"))),
            next_completed_attempt_id=by_ordinal.get((identity, row.get("next")))))
    return output


def graph_turn_state(service, conn, account_id, thread_id, turn):
    from .graph_schemas import GraphTurnState
    from .graph_selection import graph_state
    graph = graph_state(conn, thread_id)
    return GraphTurnState(thread_id=thread_id, active_branch_id=graph["active_branch_id"],
        revision=graph["revision"], turn=_turn_views(service, conn, account_id, thread_id, [turn], graph["active_branch_id"])[0])


def graph_request_accepted(service, conn, account_id, request):
    from .graph_schemas import GraphRequestAccepted
    from .graph_selection import member_turn
    attempt = conn.execute(sa.select(t.attempts).where(
        t.attempts.c.id == request["id"])).mappings().one()
    thread_id, execution_branch = request["thread_id"], attempt["branch_id"]
    turn = member_turn(conn, thread_id, attempt["turn_id"], execution_branch)
    graph = graph_state(conn, thread_id)
    return GraphRequestAccepted(thread_id=thread_id, active_branch_id=graph["active_branch_id"],
        revision=graph["revision"], execution_branch_id=execution_branch,
        turn=_turn_views(service, conn, account_id, thread_id, [turn], execution_branch)[0],
        request=service._request_view(request))


def graph_page(service, raw, thread_id, before_turn_sequence=None, branch_id=None):
    with service.engine.begin() as conn:
        account, thread = owned_thread(service, conn, raw, thread_id)
        graph = fenced_graph(conn, thread_id, branch_id)
        return project_page(service, conn, account["id"], thread, graph, before_turn_sequence)


def project_page(service, conn, account_id, thread, graph, before_turn_sequence=None):
    from .graph_schemas import GRAPH_TURN_LIMIT, GraphPage
    from .request_state import UNKNOWN_PAID_OUTCOME
    thread_id, branch_id = thread["id"], graph["active_branch_id"]
    query = sa.select(t.turns).join(t.branch_turns, t.branch_turns.c.turn_id == t.turns.c.id).where(
        t.turns.c.thread_id == thread_id, t.branch_turns.c.branch_id == branch_id)
    if before_turn_sequence is not None:
        query = query.where(t.turns.c.turn_sequence < before_turn_sequence)
    rows = conn.execute(query.order_by(t.turns.c.turn_sequence.desc())
        .limit(GRAPH_TURN_LIMIT + 1)).mappings().all()
    chosen = list(reversed(rows[:GRAPH_TURN_LIMIT]))
    active_id = conn.execute(sa.select(t.requests.c.id).where(
        t.requests.c.thread_id == thread_id,
        t.requests.c.state.in_(("pending", "streaming")))).scalar_one_or_none()
    active = _attempt_views(service, conn, thread_id, [active_id]).get(active_id) if active_id else None
    if active and active.state not in {"pending", "streaming"}:
        active = None
    # UNKNOWN is a durable whole-thread execution barrier, including requests
    # absent from this branch or any currently loaded turn page.
    unknown = conn.execute(sa.select(t.requests.c.id).where(
        t.requests.c.thread_id == thread_id, t.requests.c.error_code == UNKNOWN_PAID_OUTCOME,
        t.requests.c.state.not_in(("pending", "streaming"))).order_by(
        t.requests.c.created_at, t.requests.c.id).limit(1)).scalar_one_or_none()
    return GraphPage(thread=service._thread_view(thread), active_branch_id=branch_id,
        revision=graph["revision"], turns=_turn_views(service, conn, account_id, thread_id, chosen, branch_id),
        next_before_turn_sequence=chosen[0]["turn_sequence"] if len(rows) > GRAPH_TURN_LIMIT else None,
        active_attempt=active, unknown_request_id=unknown)


def attempt_page(service, raw, thread_id, turn_id, before_ordinal=None, branch_id=None):
    from .graph_schemas import GRAPH_ATTEMPT_LIMIT, GraphAttemptPage
    from .graph_selection import active_turn, graph_state, owned_thread
    with service.engine.begin() as conn:
        account, _ = owned_thread(service, conn, raw, thread_id)
        graph = fenced_graph(conn, thread_id, branch_id)
        turn = active_turn(conn, thread_id, turn_id, graph)
        query = sa.select(t.attempts.c.id, t.attempts.c.ordinal).select_from(
            visible_attempts(graph["active_branch_id"])).where(t.attempts.c.turn_id == turn_id,
                t.attempts.c.thread_id == thread_id)
        if before_ordinal is not None:
            query = query.where(t.attempts.c.ordinal < before_ordinal)
        rows = conn.execute(query.order_by(t.attempts.c.ordinal.desc())
            .limit(GRAPH_ATTEMPT_LIMIT + 1)).all()
        chosen = list(reversed(rows[:GRAPH_ATTEMPT_LIMIT]))
        views = _attempt_views(service, conn, thread_id, [row.id for row in chosen])
        state = graph_turn_state(service, conn, account["id"], thread_id, turn)
        return GraphAttemptPage(**state.model_dump(), attempts=[views[row.id] for row in chosen],
            next_before_ordinal=chosen[0].ordinal if len(rows) > GRAPH_ATTEMPT_LIMIT else None)
