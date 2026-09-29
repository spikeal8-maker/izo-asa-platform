"""SQLAlchemy Core auth schema. Migrations are immutable copies, never create_all on startup."""
import sqlalchemy as sa

metadata = sa.MetaData()
accounts = sa.Table("accounts", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("public_code", sa.String(16), unique=True, nullable=False),
    sa.Column("display_name", sa.String(80), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("state IN ('active','generation_suspended','security_locked','deletion_pending','deleted')", name="account_state"))
identities = sa.Table("auth_identities", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("provider", sa.String(32), nullable=False),
    sa.Column("subject", sa.String(254), nullable=False),
    sa.Column("verified_at", sa.BigInteger),
    sa.UniqueConstraint("provider", "subject", name="identity_subject"),
    sa.UniqueConstraint("account_id", "provider", name="account_identity_provider"))
passwords = sa.Table("password_credentials", metadata,
    sa.Column("identity_id", sa.Uuid, sa.ForeignKey("auth_identities.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("password_hash", sa.String(256), nullable=False))
sessions = sa.Table("account_sessions", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
    sa.Column("csrf_token", sa.String(43), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("last_seen_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False),
    sa.Column("idle_seconds", sa.Integer, nullable=False),
    sa.Column("revoked_at", sa.BigInteger),
    sa.Column("client_label", sa.String(160), nullable=False),
    sa.CheckConstraint("expires_at > created_at AND idle_seconds > 0", name="session_lifetime"))
invites = sa.Table("account_invites", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False),
    sa.Column("consumed_at", sa.BigInteger),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="SET NULL")),
    sa.CheckConstraint("expires_at > created_at", name="invite_lifetime"))
limits = sa.Table("auth_rate_limits", metadata,
    sa.Column("bucket_key", sa.String(64), primary_key=True),
    sa.Column("window_start", sa.BigInteger, primary_key=True),
    sa.Column("count", sa.Integer, nullable=False),
    sa.CheckConstraint("count > 0", name="rate_positive"))
permissions = sa.Table("account_permissions", metadata,
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("permission", sa.String(80), primary_key=True),
    sa.Column("expires_at", sa.BigInteger))
audit = sa.Table("account_audit", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="SET NULL")),
    sa.Column("action", sa.String(64), nullable=False),
    sa.Column("target_id", sa.Uuid),
    sa.Column("created_at", sa.BigInteger, nullable=False))
