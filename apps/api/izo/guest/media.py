"""Guest-owned result bytes without creating a normal account-session download ticket."""
import hashlib

from ..accounts import media_access as access
from ..media import repository as repo
from ..media.schemas import MediaError


def read_owned(auth, store, raw, asset_id):
    with auth.engine.begin() as conn:
        principal = access.context(auth, conn, raw)
        row = dict(repo.asset(conn, principal.account_id, asset_id))
    try:
        data = store.read(row["object_key"], row["byte_size"])
    except Exception:
        raise MediaError(503, "media_unavailable") from None
    if len(data) != row["byte_size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise MediaError(503, "media_integrity_error")
    with auth.engine.begin() as conn:
        principal = access.context(auth, conn, raw)
        current = repo.asset(conn, principal.account_id, asset_id)
        if current["sha256"] != row["sha256"] or current["object_key"] != row["object_key"]:
            raise MediaError(404, "not_found")
    return data
