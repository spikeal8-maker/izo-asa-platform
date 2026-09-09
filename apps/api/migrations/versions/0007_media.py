"""MEDIA-001: private image reservations, sealed assets and session-bound tickets."""
from alembic import op
import sqlalchemy as sa

revision = "0007_media"
down_revision = "0006_admin"
branch_labels = depends_on = None


def upgrade():
    op.create_table("media_uploads",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("operation_id", sa.Uuid, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("input_type", sa.String(32), nullable=False),
        sa.Column("input_size", sa.BigInteger, nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input_width", sa.Integer, nullable=False),
        sa.Column("input_height", sa.Integer, nullable=False),
        sa.Column("reserved_bytes", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("expires_at", sa.BigInteger, nullable=False),
        sa.Column("attempt_id", sa.Uuid),
        sa.Column("lease_until", sa.BigInteger),
        sa.Column("object_key", sa.String(200)),
        sa.Column("stored_hash", sa.String(64)),
        sa.Column("stored_size", sa.BigInteger),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.UniqueConstraint("account_id", "operation_id", name="media_upload_operation"),
        sa.UniqueConstraint("id", "account_id", name="media_upload_owner_identity"),
        sa.CheckConstraint("reserved_bytes >= 0 AND input_size > 0 AND expires_at > created_at", name="media_upload_bounds"),
        sa.CheckConstraint("status IN ('pending','validating','storing','ready','rejected','expired','cancelled')", name="media_upload_state"),
        sa.CheckConstraint("status NOT IN ('storing','ready') OR (object_key IS NOT NULL AND stored_hash IS NOT NULL AND stored_size > 0 AND width > 0 AND height > 0)", name="media_sealed_candidate"))
    op.create_index('ix_media_upload_owner', 'media_uploads', ['account_id', 'status'])
    op.create_table("media_assets",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("object_key", sa.String(200), unique=True, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.ForeignKeyConstraint(["id", "account_id"], ["media_uploads.id", "media_uploads.account_id"]),
        sa.CheckConstraint("byte_size > 0 AND width > 0 AND height > 0", name="media_asset_bounds"))
    op.create_index('ix_media_asset_owner', 'media_assets', ['account_id', 'created_at', 'id'])
    op.create_table("media_download_tickets",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("asset_id", sa.Uuid, sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("session_id", sa.Uuid, sa.ForeignKey("account_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.BigInteger, nullable=False))
    op.create_index('ix_media_ticket_session', 'media_download_tickets', ['session_id', 'expires_at'])


def downgrade():
    raise RuntimeError("Media metadata has external objects; use a reviewed forward migration")
