"""Reservation and finalization transactions; Accounts -> policy -> Media locks.

No database transaction spans decoding or S3. STORING is a durable intent; uncertain
writes retain their allocation until verified, never silent quota release.
"""
import hashlib
from uuid import uuid4
import sqlalchemy as sa

from ..accounts import media_access as access
from ..entitlements.service import EntitlementService
from . import codec, repository as repo, tables as t
from .reads import MediaReader
from .schemas import MediaError, UploadIntent


class MediaService(MediaReader):
    def begin(self, raw, csrf, intent: UploadIntent):
        intent = UploadIntent.model_validate(intent)
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True, write=True)
            repo.expire_unwritten(conn, p.account_id, p.now)
            fingerprint = repo.fingerprint(intent)
            old = conn.execute(sa.select(t.uploads).where(t.uploads.c.account_id == p.account_id,
                t.uploads.c.operation_id == intent.operation_id)).mappings().first()
            if old is not None:
                if old["request_hash"] != fingerprint:
                    raise MediaError(409, "idempotency_conflict")
                return repo.upload_view(old)
            plan = EntitlementService(clock=self.auth.clock).resolve(conn, p.account_id)
            if not plan.configured or not plan.policy or not plan.policy.input_count:
                raise MediaError(403, "upload_not_allowed")
            if intent.byte_size > plan.policy.upload_bytes:
                raise MediaError(413, "upload_too_large")
            used, held = repo.usage(conn, p.account_id)
            if used + held + intent.storage_bound() > plan.policy.storage_bytes:
                raise MediaError(409, "storage_quota_exceeded")
            outstanding = conn.execute(sa.select(sa.func.count()).select_from(t.uploads).where(
                t.uploads.c.account_id == p.account_id, t.uploads.c.reserved_bytes > 0)).scalar_one()
            if outstanding >= 4:
                raise MediaError(429, "upload_limit")
            # Bound intent creation even for tiny files and cancelled requests.
            recent = conn.execute(sa.select(sa.func.count()).select_from(t.uploads).where(
                t.uploads.c.account_id == p.account_id, t.uploads.c.created_at > p.now - 3600)).scalar_one()
            if recent >= 100:
                raise MediaError(429, "upload_rate_limited")
            upload_id = uuid4()
            conn.execute(sa.insert(t.uploads).values(id=upload_id, account_id=p.account_id,
                operation_id=intent.operation_id, request_hash=fingerprint,
                input_type=intent.content_type, input_size=intent.byte_size, input_hash=intent.sha256,
                input_width=intent.width, input_height=intent.height,
                reserved_bytes=intent.storage_bound(), status="pending", created_at=p.now, expires_at=p.now + 900))
            access.record(conn, p, "media.upload_created", upload_id)
            return repo.upload_view(repo.upload(conn, p.account_id, upload_id))

    def claim(self, raw, csrf, upload_id, data):
        digest = hashlib.sha256(data).hexdigest()
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True, write=True)
            repo.expire_unwritten(conn, p.account_id, p.now)
            row = repo.upload(conn, p.account_id, upload_id)
            if len(data) != row["input_size"] or digest != row["input_hash"]:
                raise MediaError(422, "upload_content_mismatch")
            if row["status"] == "ready":
                return dict(row), None
            if row["status"] not in {"pending", "validating", "storing"}:
                raise MediaError(409, "upload_closed")
            if row["status"] != "storing" and row["expires_at"] <= p.now:
                raise MediaError(409, "upload_expired")
            if row["lease_until"] is not None and row["lease_until"] > p.now:
                raise MediaError(409, "upload_busy")
            attempt = uuid4()
            state = "storing" if row["stored_hash"] else "validating"
            repo.update_upload(conn, upload_id, status=state, attempt_id=attempt, lease_until=p.now + 60)
            return dict(repo.upload(conn, p.account_id, upload_id)), attempt

    def release_attempt(self, owner, upload_id, attempt, *, rejected=False):
        # Failure handling does not trust a now-revoked session; it only releases
        # this exact worker attempt, never touches a later attempt or ready asset.
        with self.auth.engine.begin() as conn:
            from ..accounts.media_access import lock_owner
            lock_owner(conn, owner)
            row = repo.upload(conn, owner, upload_id)
            if row["attempt_id"] != attempt or row["status"] not in {"validating", "storing"}:
                return
            values = {"lease_until": 0}
            if row["status"] == "validating":
                values["status"] = "rejected" if rejected else "pending"
                if rejected:
                    values["reserved_bytes"] = 0
            repo.update_upload(conn, upload_id, **values)

    def seal(self, raw, csrf, upload_id, attempt, image):
        digest = hashlib.sha256(image.data).hexdigest()
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True, write=True)
            row = repo.upload(conn, p.account_id, upload_id)
            if row["attempt_id"] != attempt or row["status"] not in {"validating", "storing"}:
                raise MediaError(409, "stale_upload_attempt")
            if row["status"] == "validating" and (row["lease_until"] <= p.now or row["expires_at"] <= p.now):
                raise MediaError(409, "upload_expired")
            if not 0 < len(image.data) <= row["reserved_bytes"]:
                raise MediaError(413, "canonical_image_too_large")
            if row["stored_hash"] and row["stored_hash"] != digest:
                raise MediaError(409, "canonical_revision_conflict")
            key = f"assets/{p.account_id.hex}/{upload_id.hex}/image.png"
            repo.update_upload(conn, upload_id, status="storing", object_key=key,
                stored_hash=digest, stored_size=len(image.data), width=image.width, height=image.height)
            return key

    def finalize(self, raw, csrf, upload_id, data):
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True, write=True)
            row = repo.upload(conn, p.account_id, upload_id)
            if row["status"] == "ready":
                return repo.upload_view(row)
            if row["status"] != "storing":
                raise MediaError(409, "upload_not_stored")
            if len(data) != row["stored_size"] or hashlib.sha256(data).hexdigest() != row["stored_hash"]:
                raise MediaError(503, "media_integrity_error")
            conn.execute(sa.insert(t.assets).values(id=upload_id, account_id=p.account_id,
                object_key=row["object_key"], sha256=row["stored_hash"], byte_size=row["stored_size"],
                width=row["width"], height=row["height"], created_at=p.now))
            repo.update_upload(conn, upload_id, status="ready", reserved_bytes=0, lease_until=0)
            access.record(conn, p, "media.finalized", upload_id)
            return repo.upload_view(repo.upload(conn, p.account_id, upload_id))

    def submit(self, raw, csrf, upload_id, data):
        row, attempt = self.claim(raw, csrf, upload_id, data)
        if attempt is None:
            return repo.upload_view(row)
        try:
            image = codec.decode(data, row["input_type"], row["input_width"],
                                 row["input_height"], row["reserved_bytes"])
            key = self.seal(raw, csrf, upload_id, attempt, image)
            try:
                self.store.put(key, image.data, "image/png")
            except Exception:
                raise MediaError(503, "storage_write_uncertain") from None
            return self.finalize(raw, csrf, upload_id, image.data)
        except Exception as exc:
            self.release_attempt(row["account_id"], upload_id, attempt,
                rejected=isinstance(exc, MediaError) and exc.code in {
                    "invalid_image", "image_processing_limit", "canonical_image_too_large"})
            raise

    def complete(self, raw, csrf, upload_id):
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True, write=True)
            row = repo.upload(conn, p.account_id, upload_id)
            if row["status"] == "ready":
                return repo.upload_view(row)
            if row["status"] != "storing":
                raise MediaError(409, "upload_not_stored")
        try:
            data = self.store.read(row["object_key"], row["stored_size"])
        except Exception:
            raise MediaError(503, "storage_write_uncertain") from None
        return self.finalize(raw, csrf, upload_id, data)

    def cancel(self, raw, csrf, upload_id):
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True)
            row = repo.upload(conn, p.account_id, upload_id)
            if row["status"] in {"pending", "validating"}:
                repo.update_upload(conn, upload_id, status="cancelled", reserved_bytes=0)
                access.record(conn, p, "media.cancelled", upload_id)
            elif row["status"] not in {"cancelled", "expired", "rejected"}:
                raise MediaError(409, "upload_requires_reconciliation")
            return repo.upload_view(repo.upload(conn, p.account_id, upload_id))
