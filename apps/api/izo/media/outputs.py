"""Internal generation output boundary; no caller-owned object keys or SQL IO across S3."""
import hashlib
import sqlalchemy as sa
from . import tables as t
from .schemas import MediaError


def load(conn, owner, output_id):
    row = conn.execute(sa.select(t.outputs).where(t.outputs.c.id == output_id,
        t.outputs.c.account_id == owner).with_for_update()).mappings().first()
    if row is None:
        raise MediaError(404, "not_found")
    return row


def reserve(conn, owner, output_id, bound, width, height, now):
    # JOBS holds Account and verified policy/usage through this transaction.
    conn.execute(sa.insert(t.outputs).values(id=output_id, account_id=owner,
        reserved_bytes=bound, state="reserved", width=width, height=height, created_at=now))


def seal(conn, owner, output_id, data):
    row = load(conn, owner, output_id)
    digest = hashlib.sha256(data).hexdigest()
    if row["state"] != "reserved" or not 0 < len(data) <= row["reserved_bytes"]:
        raise MediaError(409, "invalid_output")
    key = f"assets/{owner.hex}/{output_id.hex}/image.png"
    conn.execute(sa.update(t.outputs).where(t.outputs.c.id == output_id).values(
        state="storing", object_key=key, sha256=digest, byte_size=len(data)))
    return key


def finalize(conn, owner, output_id, data, now):
    row = load(conn, owner, output_id)
    if row["state"] == "ready":
        return output_id
    if (row["state"] != "storing" or len(data) != row["byte_size"]
            or hashlib.sha256(data).hexdigest() != row["sha256"]):
        raise MediaError(503, "media_integrity_error")
    conn.execute(sa.insert(t.assets).values(id=output_id, output_id=output_id, account_id=owner,
        object_key=row["object_key"], sha256=row["sha256"], byte_size=len(data),
        width=row["width"], height=row["height"], created_at=now))
    conn.execute(sa.update(t.outputs).where(t.outputs.c.id == output_id)
                 .values(state="ready", reserved_bytes=0))
    return output_id


def release(conn, owner, output_id):
    row = load(conn, owner, output_id)
    if row["state"] != "reserved":
        raise MediaError(409, "output_requires_reconciliation")
    conn.execute(sa.update(t.outputs).where(t.outputs.c.id == output_id)
                 .values(state="released", reserved_bytes=0))
