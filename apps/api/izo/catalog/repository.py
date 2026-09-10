"""Small transactional helpers for CATALOG-001; result payloads never contain secret refs."""
from contextlib import contextmanager
import hashlib
import hmac
import json
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ..accounts import repository as account_repo
from . import tables as t
from .schemas import (CapabilityContent, CapabilityView, CatalogError, ChangeReceipt,
    ConnectionContent, ConnectionView, CredentialView, RevisionView)


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def fingerprint(action, actor, target, payload) -> str:
    return digest(canonical({"action": action, "actor": str(actor), "target": target, "payload": payload}))


@contextmanager
def atomic(conn):
    if not conn.in_transaction() or conn.dialect.name not in {"sqlite", "postgresql"}:
        raise RuntimeError("Catalog requires explicit supported transaction")
    try:
        with conn.begin_nested():
            yield
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505" or getattr(exc.orig, "sqlite_errorcode", None) in {1555, 2067}:
            raise CatalogError(409, "catalog_conflict") from None
        raise


def replay(conn, operation_id, expected):
    row = conn.execute(sa.select(t.changes).where(t.changes.c.operation_id == operation_id)).mappings().first()
    if row is None:
        return None
    if not hmac.compare_digest(row["fingerprint"], expected):
        raise CatalogError(409, "idempotency_conflict")
    return ChangeReceipt(operation_id=row["operation_id"], action=row["action"], target=row["target"],
        result_version=row["result_version"], result_id=row["result_id"])


def record(conn, actor, action, target, operation_id, expected, version, result_id, reason, now):
    row = dict(operation_id=operation_id, actor_id=actor, action=action, target=target,
        fingerprint=expected, result_version=version, result_id=result_id, reason=reason, created_at=now)
    conn.execute(sa.insert(t.changes).values(**row))
    account_repo.event(conn, actor, "catalog." + action, now, result_id)
    return ChangeReceipt(operation_id=operation_id, action=action, target=target,
        result_version=version, result_id=result_id)


def revision(conn, table, revision_id):
    if revision_id is None:
        return None
    return conn.execute(sa.select(table).where(table.c.id == revision_id)).mappings().first()


def head(conn, table, key_col, key, *, lock=False):
    query = sa.select(table).where(key_col == key)
    if lock:
        query = query.with_for_update()
    return conn.execute(query).mappings().first()


def active_credential(conn, connection_id, *, lock=False):
    query = sa.select(t.credential_bindings).where(
        t.credential_bindings.c.connection_id == connection_id,
        t.credential_bindings.c.revoked_at.is_(None)
    ).order_by(t.credential_bindings.c.version.desc()).limit(1)
    if lock:
        query = query.with_for_update()
    return conn.execute(query).mappings().first()


def _revision_view(row):
    if row is None:
        return None
    return RevisionView(id=row["id"], revision=row["revision"],
        content_hash=row["content_hash"], created_at=row["created_at"])


def credential_view(row):
    if row is None:
        return None
    return CredentialView(binding_id=row["id"], version=row["version"],
        source_type=row["source_type"], reference_fingerprint=hashlib.sha256(
            row["secret_ref"].encode()).hexdigest(), environment=row["environment"],
        account_ref=row["account_ref"], project_ref=row["project_ref"],
        state="revoked" if row["revoked_at"] is not None else "active",
        created_at=row["created_at"], revoked_at=row["revoked_at"])


def capability_view(conn, capability_id):
    current = head(conn, t.capability_heads, t.capability_heads.c.capability_id, capability_id)
    if current is None:
        raise CatalogError(404, "not_found")
    draft = revision(conn, t.capability_revisions, current["draft_revision_id"])
    published = revision(conn, t.capability_revisions, current["published_revision_id"])
    selected = draft or published
    content = CapabilityContent.model_validate_json(selected["content_json"]) if selected else None
    return CapabilityView(capability_id=capability_id, version=current["version"],
        draft=_revision_view(draft), published=_revision_view(published), content=content)


def connection_view(conn, connection_id, *, include_credential=False):
    current = head(conn, t.connection_heads, t.connection_heads.c.connection_id, connection_id)
    if current is None:
        raise CatalogError(404, "not_found")
    draft = revision(conn, t.connection_revisions, current["draft_revision_id"])
    published = revision(conn, t.connection_revisions, current["published_revision_id"])
    selected = draft or published
    content = ConnectionContent.model_validate_json(selected["content_json"]) if selected else None
    credential = credential_view(active_credential(conn, connection_id)) if include_credential else None
    return ConnectionView(connection_id=connection_id, version=current["version"],
        draft=_revision_view(draft), published=_revision_view(published), content=content,
        credential=credential)


def save_revision(conn, *, now, actor, operation_id, expected_version, target, reason,
                  head_table, revision_table, key_col, content, action):
    payload = {"expected_version": expected_version,
               "content": content.model_dump(mode="json"), "reason": reason}
    expected = fingerprint(action, actor, target, payload)
    old = replay(conn, operation_id, expected)
    if old:
        return old
    current = head(conn, head_table, key_col, target, lock=True)
    version = current["version"] if current else 0
    if version != expected_version:
        raise CatalogError(409, "revision_conflict")
    revision_number, revision_id = version + 1, uuid4()
    text = canonical(content.model_dump(mode="json"))
    conn.execute(sa.insert(revision_table).values(id=revision_id, **{key_col.name: target},
        revision=revision_number, content_json=text, content_hash=digest(text), created_at=now))
    if current:
        conn.execute(sa.update(head_table).where(key_col == target).values(
            version=revision_number, draft_revision_id=revision_id))
    else:
        values = {key_col.name: target, "version": revision_number, "draft_revision_id": revision_id}
        if head_table is t.connection_heads:
            values["runtime_state"] = "disabled"
        conn.execute(sa.insert(head_table).values(**values))
    return record(conn, actor, action, target, operation_id, expected, revision_number,
                  revision_id, reason, now)
