"""Media schema: reservations precede external writes; ready assets are private."""
import sqlalchemy as sa

metadata = sa.MetaData()
sa.Table("accounts", metadata, sa.Column("id", sa.Uuid, primary_key=True))
sa.Table("account_sessions", metadata, sa.Column("id", sa.Uuid, primary_key=True))
uploads = sa.Table("media_uploads", metadata,
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
sa.Index("ix_media_upload_owner", uploads.c.account_id, uploads.c.status)
assets = sa.Table("media_assets", metadata,
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
sa.Index("ix_media_asset_owner", assets.c.account_id, assets.c.created_at, assets.c.id)
tickets = sa.Table("media_download_tickets", metadata,
    sa.Column("token_hash", sa.String(64), primary_key=True),
    sa.Column("asset_id", sa.Uuid, sa.ForeignKey("media_assets.id"), nullable=False),
    sa.Column("session_id", sa.Uuid, sa.ForeignKey("account_sessions.id", ondelete="CASCADE"), nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False))
sa.Index("ix_media_ticket_session", tickets.c.session_id, tickets.c.expires_at)
TABLES = (uploads, assets, tickets)
