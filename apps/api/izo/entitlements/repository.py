"""Small persistence helpers; all writes require an explicit outer transaction."""
from contextlib import contextmanager
import hashlib
import hmac
import json

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from . import tables as t
from .schemas import EntitlementError, ChangeReceipt, PlanPolicy
from ..accounts import entitlement_access as access


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@contextmanager
def atomic(conn):
    if not conn.in_transaction() or conn.dialect.name not in {"postgresql", "sqlite"}:
        raise RuntimeError("Entitlements requires a supported explicit transaction")
    try:
        with conn.begin_nested():
            yield
    except IntegrityError as exc:
        if (getattr(exc.orig, "sqlstate", None) == "23505"
                or getattr(exc.orig, "sqlite_errorcode", None) in {1555, 2067}):
            raise EntitlementError(409, "entitlement_conflict") from None
        raise


def fingerprint(action, actor, target, command):
    return digest(canonical({"action": action, "actor": str(actor),
        "target": str(target) if target else None, "command": command.model_dump(mode="json")}))


def receipt(row):
    return ChangeReceipt(operation_id=row["operation_id"], action=row["action"],
        revision_id=row["revision_id"], target_id=row["target_id"], version=row["result_version"])


def replay(conn, operation_id, expected):
    row = conn.execute(sa.select(t.changes).where(
        t.changes.c.operation_id == operation_id)).mappings().first()
    if row is None:
        return None
    if not hmac.compare_digest(row["fingerprint"], expected):
        raise EntitlementError(409, "idempotency_conflict")
    return receipt(row)


def record(conn, actor, target, action, command, expected, version, now):
    row = dict(operation_id=command.operation_id, actor_id=actor, target_id=target,
        action=action, revision_id=command.revision_id, fingerprint=expected,
        reason=command.reason, result_version=version, created_at=now)
    conn.execute(sa.insert(t.changes).values(**row))
    access.record_event(conn, command.operation_id, actor, action,
                        target or command.revision_id, now)
    return receipt(row)


def revision(conn, revision_id):
    row = conn.execute(sa.select(t.revisions).where(
        t.revisions.c.id == revision_id)).mappings().first()
    if row is None:
        raise EntitlementError(404, "plan_not_found")
    try:
        if not hmac.compare_digest(digest(row["policy_json"]), row["policy_hash"]):
            raise ValueError("Policy hash mismatch")
        policy = PlanPolicy.model_validate_json(row["policy_json"])
    except (ValueError, ValidationError):
        raise EntitlementError(503, "invalid_policy") from None
    return row, policy
