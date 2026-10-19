"""One admission owner for original sends and same-turn regeneration."""
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .credentials import ChatError
from .conversations import persist_request
from .graph_schemas import GraphRequestAccepted
from .graph_selection import active_turn, check_revision
from .graph_selection import graph_state, owned_thread
from .request_state import UNKNOWN_PAID_OUTCOME
from .schemas import MODEL_REVISION, OPENROUTER_AUTO_MODEL, REQUEST_WINDOW_LIMIT, RequestCreate


def _expire_pending(service, raw, csrf, thread_id):
    # Preserve the old committed expiry boundary, even if later replay conflicts.
    with service.engine.begin() as conn:
        owned_thread(service, conn, raw, thread_id, csrf, mutation=True)
        now = service.now()
        expired = conn.execute(sa.update(t.requests).where(
            t.requests.c.thread_id == thread_id, t.requests.c.state == "pending",
            t.requests.c.deadline_at <= now).values(state="interrupted",
            error_code="request_expired", updated_at=now).returning(t.requests.c.id)).scalars().all()
        if expired:
            conn.execute(sa.update(t.messages).where(t.messages.c.request_id.in_(expired),
                t.messages.c.role == "assistant").values(state="interrupted", updated_at=now))


def _accepted(service, conn, account_id, row, turn_id):
    from .history_pages import graph_turn_state
    if turn_id is None:
        return service._request_view(row)
    turn = conn.execute(sa.select(t.turns).where(t.turns.c.id == turn_id,
        t.turns.c.thread_id == row["thread_id"])).mappings().one()
    state = graph_turn_state(service, conn, account_id, row["thread_id"], turn)
    return GraphRequestAccepted(**state.model_dump(), request=service._request_view(row))


def _replay(service, conn, account_id, thread_id, command, turn_id, *, owned_only=False):
    query = sa.select(t.requests).where(t.requests.c.id == command.request_id)
    if owned_only:
        query = query.where(t.requests.c.account_id == account_id, t.requests.c.thread_id == thread_id)
    row = conn.execute(query).mappings().first()
    if row is None:
        return None
    if row["account_id"] != account_id or row["thread_id"] != thread_id:
        raise ChatError(404, "request_not_found")
    context = conn.execute(sa.select(t.contexts).where(
        t.contexts.c.request_id == row["id"])).mappings().one()
    if turn_id is not None:
        attempt = conn.execute(sa.select(t.attempts).where(
            t.attempts.c.id == row["id"])).mappings().one()
        valid = (context["kind"] == "regenerate" and attempt["turn_id"] == turn_id
                 and attempt["branch_id"] == command.branch_id
                 and attempt["source_attempt_id"] == command.source_attempt_id)
    else:
        expected = service._request_fingerprint(thread_id, command.text, command.model,
            row["connection_id"], row["credential_generation"], row["model_revision"], command.attachment_ids)
        valid = context["kind"] == "send" and row["fingerprint"] == expected
    if not valid:
        raise ChatError(409, "request_conflict")
    return _accepted(service, conn, account_id, row, turn_id)


def _material(service, conn, account_id, thread_id, command, turn_id):
    if conn.execute(sa.select(t.requests.c.id).where(
        t.requests.c.thread_id == thread_id, t.requests.c.error_code == UNKNOWN_PAID_OUTCOME
    ).limit(1)).first():
        raise ChatError(409, UNKNOWN_PAID_OUTCOME)
    if turn_id is None:
        return command, None
    graph = graph_state(conn, thread_id)
    turn = active_turn(conn, thread_id, turn_id, graph)
    source = conn.execute(sa.select(t.requests.c.model, t.requests.c.state).join(
        t.attempts, t.attempts.c.id == t.requests.c.id).where(
        t.attempts.c.id == command.source_attempt_id, t.attempts.c.turn_id == turn_id,
        t.attempts.c.thread_id == thread_id,
        t.attempts.c.branch_id == graph["active_branch_id"])).mappings().first()
    if source is None:
        raise ChatError(404, "attempt_not_found")
    check_revision(graph, command)
    selected = conn.execute(sa.select(t.selections.c.attempt_id).where(
        t.selections.c.turn_id == turn_id)).scalar_one_or_none()
    if source["state"] != "completed" or selected != command.source_attempt_id:
        raise ChatError(409, "source_attempt_not_selected")
    user = conn.execute(sa.select(t.messages).where(
        t.messages.c.id == turn["user_message_id"])).mappings().one()
    attached = service._attachments_for_messages(conn, account_id, [user["id"]]).get(user["id"], ())
    return RequestCreate(request_id=command.request_id, model=source["model"],
        text=user["content"], attachment_ids=[item["asset_id"] for item in attached]), turn


def _admission(service, conn, account_id, material, dynamic):
    head, allowed = service.catalog.public_text(conn, lock=True)
    if material.model == OPENROUTER_AUTO_MODEL:
        provider, vision = "openrouter", False
    elif "/" in material.model:
        if dynamic is None:
            raise ChatError(409, "request_conflict")
        provider, _, vision = dynamic
    else:
        model = next((item for item in allowed if item.id == material.model), None)
        if model is None:
            raise ChatError(422, "model_not_allowed")
        provider = model.provider
        vision = service.static_vision_supported(model.id, provider)
    if material.attachment_ids and not vision:
        raise ChatError(422, "model_vision_unsupported")
    assets = service._attachment_assets(conn, account_id, material.attachment_ids)
    service._consume_rate(conn, account_id, "request", REQUEST_WINDOW_LIMIT)
    connection = conn.execute(sa.select(t.connections).where(
        t.connections.c.account_id == account_id, t.connections.c.provider == provider
    ).with_for_update()).mappings().first()
    if not connection or not connection["enabled"] or connection["verified_at"] is None:
        raise ChatError(409, "credential_not_verified")
    revision = (f"{MODEL_REVISION}:catalog-{head['revision']}"
                if provider == "deepseek" else f"{MODEL_REVISION}:openrouter")
    return connection, revision, vision, assets


def admit_request(service, raw, csrf, thread_id, command, turn_id=None):
    _expire_pending(service, raw, csrf, thread_id)
    with service.engine.begin() as conn:
        account, _ = owned_thread(service, conn, raw, thread_id, csrf, mutation=True)
        replay = _replay(service, conn, account["id"], thread_id, command, turn_id, owned_only=True)
        if replay is not None:
            return replay
        material, _ = _material(service, conn, account["id"], thread_id, command, turn_id)
    # Remote catalog resolution never holds a thread/database lock; the full
    # source selection and revision are checked again before durable admission.
    dynamic = service.model_admission(material.model) if "/" in material.model else None
    try:
        with service.engine.begin() as conn:
            account, thread = owned_thread(service, conn, raw, thread_id, csrf, mutation=True)
            replay = _replay(service, conn, account["id"], thread_id, command, turn_id)
            if replay is not None:
                return replay
            material, turn = _material(service, conn, account["id"], thread_id, command, turn_id)
            admission = _admission(service, conn, account["id"], material, dynamic)
            row, result_turn = persist_request(service, conn, account["id"], thread, command, material, turn, admission)
            return _accepted(service, conn, account["id"], row, result_turn)
    except IntegrityError as exc:
        raise ChatError(409, "active_request_exists") from exc
