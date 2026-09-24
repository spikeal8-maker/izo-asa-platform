"""Bounded server-side materialization of durable Chat image context."""
import base64
import hashlib

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .schemas import MAX_CONTEXT_IMAGE_BYTES


class VisionContextMixin:
    def _vision_rows(self, conn, account_id, message_ids, model):
        if not message_ids or not self.policy.model_supports_vision(model):
            return {}
        count = conn.execute(sa.select(sa.func.count()).select_from(t.attachments).where(
            t.attachments.c.account_id == account_id,
            t.attachments.c.message_id.in_(message_ids))).scalar_one()
        if not count:
            return {}
        rows = conn.execute(sa.select(
            t.attachments, t.media_assets.c.object_key).select_from(
                t.attachments.join(
                    t.media_assets,
                    t.attachments.c.asset_id == t.media_assets.c.id)).where(
                t.attachments.c.account_id == account_id,
                t.media_assets.c.account_id == account_id,
                t.attachments.c.message_id.in_(message_ids)).order_by(
                t.attachments.c.message_id,
                t.attachments.c.ordinal)).mappings().all()
        grouped = {}
        for row in rows:
            grouped.setdefault(row["message_id"], []).append(dict(row))
        return grouped

    @staticmethod
    def _bounded_context(prior, user, grouped, max_chars):
        used_chars = len(user["content"])
        used_images = sum(
            item["byte_size"] for item in grouped.get(user["id"], ()))
        chosen = []
        for item in prior:
            image_bytes = sum(
                entry["byte_size"] for entry in grouped.get(item["id"], ()))
            if (used_chars + len(item["content"]) > max_chars
                    or used_images + image_bytes > MAX_CONTEXT_IMAGE_BYTES):
                break
            chosen.append(dict(item))
            used_chars += len(item["content"])
            used_images += image_bytes
        chosen.reverse()
        chosen.append(dict(user))
        return chosen

    def _provider_message(self, item, grouped):
        attached = grouped.get(item["id"], ())
        if not attached:
            return {"role": item["role"], "content": item["content"]}
        if self.media_store is None:
            raise ChatError(503, "attachment_unavailable")
        parts = [{"type": "text", "text": item["content"]}]
        for attachment in attached:
            try:
                data = self.media_store.read(
                    attachment["object_key"], attachment["byte_size"])
            except Exception:
                raise ChatError(503, "attachment_unavailable") from None
            if (len(data) != attachment["byte_size"]
                    or hashlib.sha256(data).hexdigest() != attachment["sha256"]):
                raise ChatError(503, "attachment_integrity_error")
            encoded = base64.b64encode(data).decode("ascii")
            parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encoded}",
                    "detail": "auto",
                },
            })
        return {"role": item["role"], "content": parts}
