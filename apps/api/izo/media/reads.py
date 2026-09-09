"""Owner-only reads and short-lived, session-bound download grants."""
import hashlib
from uuid import UUID
import sqlalchemy as sa

from ..accounts import media_access as access
from ..accounts.security import TOKEN, token, token_hash
from . import repository as repo, tables as t
from .schemas import AssetList, DownloadView, MediaError


class MediaReader:
    def __init__(self, auth, store):
        self.auth, self.store = auth, store

    def status(self, raw, upload_id):
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw)
            repo.expire_unwritten(conn, p.account_id, p.now)
            return repo.upload_view(repo.upload(conn, p.account_id, upload_id))

    def get(self, raw, asset_id):
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw)
            return repo.asset_view(repo.asset(conn, p.account_id, asset_id))

    def list(self, raw, limit=20, offset=0):
        if type(limit) is not int or type(offset) is not int or not 1 <= limit <= 50 or not 0 <= offset <= 10000:
            raise MediaError(422, "invalid_input")
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw)
            repo.expire_unwritten(conn, p.account_id, p.now)
            rows = conn.execute(sa.select(t.assets).where(t.assets.c.account_id == p.account_id)
                .order_by(t.assets.c.created_at.desc(), t.assets.c.id.desc())
                .offset(offset).limit(limit + 1)).mappings().all()
            used, reserved = repo.usage(conn, p.account_id)
            return AssetList(assets=[repo.asset_view(row) for row in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
                used_bytes=used, reserved_bytes=reserved)

    def ticket(self, raw, csrf, asset_id):
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True)
            repo.asset(conn, p.account_id, asset_id)
            conn.execute(sa.delete(t.tickets).where(t.tickets.c.session_id == p.session_id,
                                                   t.tickets.c.expires_at <= p.now))
            count = conn.execute(sa.select(sa.func.count()).select_from(t.tickets).where(
                t.tickets.c.session_id == p.session_id)).scalar_one()
            if count >= 20:
                raise MediaError(429, "download_limit")
            secret = token()
            conn.execute(sa.insert(t.tickets).values(token_hash=token_hash(secret),
                asset_id=asset_id, session_id=p.session_id, expires_at=p.now + 120))
            return DownloadView(url=f"/api/v1/media/assets/{asset_id}/content?ticket={secret}",
                                expires_at=p.now + 120)

    def _download_record(self, conn, raw, asset_id, secret):
        p = access.context(self.auth, conn, raw)
        row = repo.asset(conn, p.account_id, asset_id)
        grant = conn.execute(sa.select(t.tickets).where(t.tickets.c.token_hash == token_hash(secret),
            t.tickets.c.asset_id == asset_id, t.tickets.c.session_id == p.session_id,
            t.tickets.c.expires_at > p.now)).first()
        if grant is None:
            raise MediaError(404, "not_found")
        return row

    def download(self, raw, asset_id: UUID, secret: str):
        if not TOKEN.fullmatch(secret):
            raise MediaError(404, "not_found")
        with self.auth.engine.begin() as conn:
            row = self._download_record(conn, raw, asset_id, secret)
        try:
            data = self.store.read(row["object_key"], row["byte_size"])
        except Exception:
            raise MediaError(503, "media_unavailable") from None
        if len(data) != row["byte_size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise MediaError(503, "media_integrity_error")
        # Do not hold a database lock across S3 IO. Revalidate before publishing
        # bytes; a revoked/expired session or ticket does not survive this read.
        with self.auth.engine.begin() as conn:
            self._download_record(conn, raw, asset_id, secret)
        return data
