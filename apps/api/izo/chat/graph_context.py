"""Frozen selected-prefix context; legacy provenance is captured only at claim."""
import hashlib
import json
from uuid import UUID

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .graph_selection import graph_state
from .schemas import MAX_CONTEXT_CHARS, MAX_CONTEXT_MESSAGES, MAX_CONTEXT_IMAGE_BYTES
from .schemas import MAX_OUTPUT_TOKENS

RUSSIAN_REPLY_PREFERENCE = (
    "Отвечай на русском языке, если пользователь явно не попросил другой язык. "
    "Сохраняй исходный язык кода, цитат и имён собственных."
)
CONTEXT_VERSION = "selected-turn-prefix-v1"


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def attachment_facts(rows):
    return [{"id": str(row["id"]), "asset_id": str(row["asset_id"]),
             "sha256": row["sha256"], "byte_size": row["byte_size"],
             "width": row["width"], "height": row["height"],
             "ordinal": row["ordinal"]} for row in rows]


def freeze_context(service, conn, request_row, turn, kind, provenance="admission"):
    branch_id = conn.execute(sa.select(t.attempts.c.branch_id).where(
        t.attempts.c.id == request_row["id"])).scalar_one()
    # Only complete selected turn groups are eligible. The current turn's old
    # attempt and all later turns are deliberately outside this predicate.
    prior = conn.execute(sa.select(t.turns.c.user_message_id,
        t.attempts.c.assistant_message_id).select_from(t.turns.join(
        t.branch_turns, t.branch_turns.c.turn_id == t.turns.c.id).join(
        t.selections, sa.and_(t.selections.c.turn_id == t.turns.c.id,
                             t.selections.c.branch_id == t.branch_turns.c.branch_id)).join(
        t.attempts, t.attempts.c.id == t.selections.c.attempt_id).join(
        t.requests, t.requests.c.id == t.attempts.c.id)).where(
        t.branch_turns.c.branch_id == branch_id,
        t.turns.c.thread_id == turn["thread_id"],
        t.turns.c.turn_sequence < turn["turn_sequence"],
        t.requests.c.state == "completed").order_by(
        t.turns.c.turn_sequence.desc()).limit(MAX_CONTEXT_MESSAGES // 2)).all()
    ids = [turn["user_message_id"], *[identity for pair in prior for identity in pair]]
    rows = conn.execute(sa.select(t.messages).where(t.messages.c.id.in_(ids),
        t.messages.c.thread_id == turn["thread_id"])).mappings().all()
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(set(ids)) or any(row["state"] != "complete" for row in rows):
        raise ChatError(409, "context_unavailable")
    grouped = (service._attachments_for_messages(conn, request_row["account_id"], ids)
               if request_row["vision_admitted"] else {})
    current = by_id[turn["user_message_id"]]
    used_chars = len(current["content"])
    used_images = sum(item["byte_size"] for item in grouped.get(current["id"], ()))
    if used_chars > MAX_CONTEXT_CHARS or used_images > MAX_CONTEXT_IMAGE_BYTES:
        raise ChatError(413, "context_too_large")
    chosen_groups = []
    for pair in prior:
        pair_chars = sum(len(by_id[identity]["content"]) for identity in pair)
        pair_images = sum(item["byte_size"] for identity in pair
                          for item in grouped.get(identity, ()))
        if (used_chars + pair_chars > MAX_CONTEXT_CHARS
                or used_images + pair_images > MAX_CONTEXT_IMAGE_BYTES):
            break
        chosen_groups.append(pair)
        used_chars += pair_chars
        used_images += pair_images
    chosen = [by_id[identity] for pair in reversed(chosen_groups) for identity in pair]
    chosen.append(current)
    snapshot = {
        "version": CONTEXT_VERSION, "system": RUSSIAN_REPLY_PREFERENCE,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_context_chars": MAX_CONTEXT_CHARS,
        "max_prior_messages": MAX_CONTEXT_MESSAGES,
        "max_image_bytes": MAX_CONTEXT_IMAGE_BYTES,
        "messages": [{"id": str(row["id"]), "role": row["role"],
                      "content_digest": digest(row["content"]),
                      "attachments": attachment_facts(grouped.get(row["id"], ()))}
                     for row in chosen],
    }
    values = dict(thread_id=turn["thread_id"], turn_id=turn["id"],
                  branch_id=branch_id, kind=kind, provenance=provenance,
                  revision=graph_state(conn, turn["thread_id"])["revision"],
                  snapshot=snapshot, digest=digest(snapshot))
    if provenance == "admission":
        conn.execute(sa.insert(t.contexts).values(request_id=request_row["id"], **values))
    else:
        changed = conn.execute(sa.update(t.contexts).where(
            t.contexts.c.request_id == request_row["id"],
            t.contexts.c.provenance == "legacy_unrecorded").values(**values))
        if changed.rowcount != 1:
            raise ChatError(409, "context_conflict")


def freeze_legacy_claim(service, conn, request_row):
    context = conn.execute(sa.select(t.contexts).where(
        t.contexts.c.request_id == request_row["id"])).mappings().one()
    if context["provenance"] != "legacy_unrecorded":
        return
    turn = conn.execute(sa.select(t.turns).where(
        t.turns.c.id == context["turn_id"])).mappings().one()
    freeze_context(service, conn, request_row, turn, context["kind"], "legacy_claim")


def read_snapshot(conn, request_id):
    context = conn.execute(sa.select(t.contexts).where(
        t.contexts.c.request_id == request_id)).mappings().first()
    if (context is None or context["provenance"] == "legacy_unrecorded"
            or context["snapshot"] is None or context["digest"] != digest(context["snapshot"])
            or context["snapshot"].get("version") != CONTEXT_VERSION):
        raise ChatError(503, "context_unavailable")
    return context["snapshot"]


def load_context(service, conn, account_id, request_row):
    snapshot = read_snapshot(conn, request_row["id"])
    ids = [UUID(item["id"]) for item in snapshot["messages"]]
    rows = conn.execute(sa.select(t.messages).where(t.messages.c.id.in_(ids),
        t.messages.c.thread_id == request_row["thread_id"])).mappings().all()
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(ids):
        raise ChatError(503, "context_unavailable")
    grouped = (service._vision_rows(conn, account_id, ids)
               if request_row["vision_admitted"] else {})
    chosen = []
    for identity, expected in zip(ids, snapshot["messages"], strict=True):
        row = by_id[identity]
        if (row["state"] != "complete" or row["role"] != expected["role"]
                or digest(row["content"]) != expected["content_digest"]
                or attachment_facts(grouped.get(identity, ())) != expected["attachments"]):
            raise ChatError(503, "context_integrity_error")
        chosen.append(row)
    return snapshot, chosen, grouped
