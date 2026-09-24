"""CHAT-VISION-001: durable owner-scoped Media references on user messages."""
from alembic import op
import sqlalchemy as sa

revision = "0013_chat_vision"
down_revision = "0012_chat"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "chat_message_attachments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("message_id", sa.Uuid,
                  sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.Uuid,
                  sa.ForeignKey("chat_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Uuid,
                  sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Uuid, sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("ordinal", sa.SmallInteger, nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("message_id", "ordinal", name="chat_attachment_ordinal"),
        sa.UniqueConstraint("message_id", "asset_id", name="chat_attachment_asset_once"),
        sa.CheckConstraint(
            "ordinal >= 0 AND media_type = 'image/png' AND byte_size > 0 "
            "AND width > 0 AND height > 0",
            name="chat_attachment_shape"),
    )
    op.create_index(
        "ix_chat_attachment_request", "chat_message_attachments",
        ["request_id", "ordinal"])


def downgrade():
    raise RuntimeError(
        "Chat attachment history is retained; use a reviewed forward migration")
