"""Persist account-owned normalized image references and vision admission."""
import sqlalchemy as sa
from alembic import op

revision = "0015_chat_vision"
down_revision = "0014_chat_multi_provider"
branch_labels = depends_on = None


def upgrade():
    op.add_column("chat_requests", sa.Column(
        "vision_admitted", sa.Boolean(), nullable=False,
        server_default=sa.false()))
    op.create_table(
        "chat_message_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["request_id"], ["chat_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["media_assets.id"]),
        sa.UniqueConstraint("message_id", "ordinal", name="chat_attachment_ordinal"),
        sa.UniqueConstraint("message_id", "asset_id", name="chat_attachment_asset_once"),
        sa.CheckConstraint(
            "ordinal >= 0 AND media_type = 'image/png' AND byte_size > 0 AND width > 0 AND height > 0",
            name="chat_attachment_shape"),
    )
    op.create_index("ix_chat_attachment_request", "chat_message_attachments",
                    ["request_id", "ordinal"])


def downgrade():
    raise RuntimeError("Chat image references are retained; use a reviewed forward migration")
