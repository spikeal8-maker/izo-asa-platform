"""Owner-filtered metadata; call only after the shared Accounts row lock."""
import hashlib
import json
import sqlalchemy as sa
from . import tables as t
from .schemas import AssetView, UploadView, MediaError


def fingerprint(intent):
    return hashlib.sha256(json.dumps(intent.model_dump(mode="json"), sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def upload(conn, owner, upload_id):
    row = conn.execute(sa.select(t.uploads).where(t.uploads.c.id == upload_id,
        t.uploads.c.account_id == owner).with_for_update()).mappings().first()
    if row is None:
        raise MediaError(404, "not_found")
    return row


def asset(conn, owner, asset_id):
    row = conn.execute(sa.select(t.assets).where(t.assets.c.id == asset_id,
        t.assets.c.account_id == owner)).mappings().first()
    if row is None:
        raise MediaError(404, "not_found")
    return row


def upload_view(row):
    return UploadView(id=row["id"], status=row["status"], expires_at=row["expires_at"],
        reserved_bytes=row["reserved_bytes"], asset_id=row["id"] if row["status"] == "ready" else None)


def asset_view(row):
    return AssetView(**{k: row[k] for k in ("id", "sha256", "byte_size", "width", "height", "created_at")})


def expire_unwritten(conn, owner, now):
    # A validating attempt can no longer seal after this state change. STORING
    # is never expired automatically: a timed-out external write may exist.
    conn.execute(sa.update(t.uploads).where(t.uploads.c.account_id == owner,
        t.uploads.c.expires_at <= now, sa.or_(t.uploads.c.status == "pending",
        sa.and_(t.uploads.c.status == "validating", t.uploads.c.lease_until <= now)))
        .values(status="expired", reserved_bytes=0))


def usage(conn, owner):
    used = conn.execute(sa.select(sa.func.coalesce(sa.func.sum(t.assets.c.byte_size), 0))
        .where(t.assets.c.account_id == owner)).scalar_one()
    held = conn.execute(sa.select(sa.func.coalesce(sa.func.sum(t.uploads.c.reserved_bytes), 0))
        .where(t.uploads.c.account_id == owner)).scalar_one()
    output_held = conn.execute(sa.select(sa.func.coalesce(sa.func.sum(t.outputs.c.reserved_bytes), 0))
        .where(t.outputs.c.account_id == owner)).scalar_one()
    return int(used), int(held) + int(output_held)


def update_upload(conn, upload_id, **values):
    conn.execute(sa.update(t.uploads).where(t.uploads.c.id == upload_id).values(**values))
