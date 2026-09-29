"""Bounded server-side materialization of private image context."""
import base64
import hashlib

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .schemas import MAX_CONTEXT_IMAGE_BYTES


class VisionContextMixin:
    @staticmethod
    def _vision_rows(conn, account_id, message_ids):
        if not message_ids:
            return {}
        expected = conn.execute(sa.select(
            t.attachments.c.message_id, sa.func.count().label("count")).where(
            t.attachments.c.account_id == account_id,
            t.attachments.c.message_id.in_(message_ids)).group_by(
            t.attachments.c.message_id)).all()
        if not expected:
            return {}
        rows = conn.execute(sa.select(t.attachments, t.media_assets.c.object_key).select_from(
            t.attachments.join(t.media_assets,
                               t.attachments.c.asset_id == t.media_assets.c.id)).where(
            t.attachments.c.account_id == account_id,
            t.media_assets.c.account_id == account_id,
            t.attachments.c.message_id.in_(message_ids)).order_by(
            t.attachments.c.message_id, t.attachments.c.ordinal)).mappings().all()
        grouped = {}
        for row in rows:
            grouped.setdefault(row["message_id"], []).append(row)
        if any(len(grouped.get(message_id, ())) != count
               for message_id, count in expected):
            raise ChatError(503, "attachment_unavailable")
        return grouped

    @staticmethod
    def _bounded_context(prior, user, grouped, max_chars):
        used_chars = len(user["content"])
        used_images = sum(row["byte_size"] for row in grouped.get(user["id"], ()))
        if used_images > MAX_CONTEXT_IMAGE_BYTES:
            raise ChatError(413, "image_context_too_large")
        chosen = []
        for item in prior:
            image_bytes = sum(row["byte_size"] for row in grouped.get(item["id"], ()))
            if (used_chars + len(item["content"]) > max_chars
                    or used_images + image_bytes > MAX_CONTEXT_IMAGE_BYTES):
                break
            chosen.append(item)
            used_chars += len(item["content"])
            used_images += image_bytes
        chosen.reverse()
        chosen.append(user)
        return chosen

    def _provider_message(self, item, grouped):
        attached = grouped.get(item["id"], ())
        if not attached:
            return {"role": item["role"], "content": item["content"]}
        if self.media_store is None:
            raise ChatError(503, "attachment_unavailable")
        parts = [{"type": "text", "text": item["content"]}]
        for row in attached:
            try:
                data = self.media_store.read(row["object_key"], row["byte_size"])
            except Exception:
                raise ChatError(503, "attachment_unavailable") from None
            if (len(data) != row["byte_size"]
                    or hashlib.sha256(data).hexdigest() != row["sha256"]):
                raise ChatError(503, "attachment_integrity_error")
            parts.append({"type": "image_url", "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(data).decode("ascii"),
                "detail": "auto"}})
        return {"role": item["role"], "content": parts}
