"""Development-only local-preview Media entitlement bootstrap."""
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa

from ..accounts import entitlement_access as access
from . import repository as repo, tables as t
from .schemas import EntitlementError, PlanPolicy

LOCAL_PREVIEW_MEDIA_REVISION_ID = uuid5(
    NAMESPACE_URL, "izo-asa/local-preview/chat-media/v1")
LOCAL_PREVIEW_MEDIA_REVISION = 2_000_000_000
LOCAL_PREVIEW_MEDIA_POLICY = PlanPolicy(
    input_count=5,
    upload_bytes=12 * 1024 * 1024,
    storage_bytes=256 * 1024 * 1024,
)


def ensure_local_preview_media(
        conn, account_id: UUID, *, environment: str,
        local_preview_enabled: bool, now: int) -> bool:
    """Ensure one bounded assignment only for explicit development preview."""
    if environment != "development" or not local_preview_enabled:
        return False
    states = access.locked_states(conn, [account_id])
    if states.get(account_id) != "active" or not access.verified(conn, account_id):
        raise EntitlementError(403, "local_preview_entitlement_forbidden")

    policy_json = repo.canonical(
        LOCAL_PREVIEW_MEDIA_POLICY.model_dump(mode="json"))
    policy_hash = repo.digest(policy_json)
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif conn.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError("Unsupported local-preview entitlement database")
    conn.execute(insert(t.revisions).values(
        id=LOCAL_PREVIEW_MEDIA_REVISION_ID,
        plan_code="custom",
        revision=LOCAL_PREVIEW_MEDIA_REVISION,
        policy_json=policy_json,
        policy_hash=policy_hash,
        created_at=now,
    ).on_conflict_do_nothing())
    revision = conn.execute(sa.select(t.revisions).where(
        t.revisions.c.id == LOCAL_PREVIEW_MEDIA_REVISION_ID
    ).with_for_update()).mappings().first()
    if revision is None or (
        revision["plan_code"] != "custom"
        or revision["revision"] != LOCAL_PREVIEW_MEDIA_REVISION
        or revision["policy_json"] != policy_json
        or revision["policy_hash"] != policy_hash
    ):
        raise EntitlementError(503, "local_preview_entitlement_conflict")

    assignment = conn.execute(sa.select(t.assignments).where(
        t.assignments.c.account_id == account_id
    ).with_for_update()).mappings().first()

    if assignment is None:
        conn.execute(sa.insert(t.assignments).values(
            account_id=account_id,
            revision_id=LOCAL_PREVIEW_MEDIA_REVISION_ID,
            starts_at=0,
            expires_at=None,
            version=1,
        ))
    elif (
        assignment["revision_id"] != LOCAL_PREVIEW_MEDIA_REVISION_ID
        or assignment["starts_at"] != 0
        or assignment["expires_at"] is not None
    ):
        raise EntitlementError(503, "local_preview_entitlement_conflict")
    return True
