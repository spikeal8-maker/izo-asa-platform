"""Account-scoped references to ready, normalized shared Media assets."""
from uuid import uuid4

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .schemas import AttachmentView, MAX_CHAT_IMAGE_BYTES, MAX_CONTEXT_IMAGE_BYTES


class AttachmentMixin:
    @staticmethod
    def _attachment_view(row) -> AttachmentView:
        return AttachmentView(
            id=row["id"], asset_id=row["asset_id"],
            media_type=row["media_type"], byte_size=row["byte_size"],
            width=row["width"], height=row["height"], sha256=row["sha256"],
            created_at=row["created_at"])

    def _attachments_for_messages(self, conn, account_id, message_ids):
        if not message_ids:
            return {}
        rows = conn.execute(sa.select(t.attachments).where(
            t.attachments.c.account_id == account_id,
            t.attachments.c.message_id.in_(message_ids)).order_by(
            t.attachments.c.message_id, t.attachments.c.ordinal)).mappings()
        grouped = {}
        for row in rows:
            grouped.setdefault(row["message_id"], []).append(row)
        return grouped

    @staticmethod
    def _attachment_assets(conn, account_id, attachment_ids):
        if not attachment_ids:
            return []
        rows = conn.execute(sa.select(t.media_assets).where(
            t.media_assets.c.account_id == account_id,
            t.media_assets.c.id.in_(attachment_ids))).mappings().all()
        by_id = {row["id"]: row for row in rows}
        if len(by_id) != len(attachment_ids):
            raise ChatError(404, "attachment_not_found")
        ordered = [by_id[asset_id] for asset_id in attachment_ids]
        if any(row["byte_size"] > MAX_CHAT_IMAGE_BYTES for row in ordered):
            raise ChatError(413, "image_too_large")
        if sum(row["byte_size"] for row in ordered) > MAX_CONTEXT_IMAGE_BYTES:
            raise ChatError(413, "image_context_too_large")
        return ordered

    @staticmethod
    def _insert_attachments(conn, account_id, request_id, message_id, assets, now):
        if assets:
            conn.execute(sa.insert(t.attachments), [dict(
                id=uuid4(), message_id=message_id, request_id=request_id,
                account_id=account_id, asset_id=asset["id"], ordinal=ordinal,
                media_type="image/png", byte_size=asset["byte_size"],
                width=asset["width"], height=asset["height"],
                sha256=asset["sha256"], created_at=now,
            ) for ordinal, asset in enumerate(assets)])
