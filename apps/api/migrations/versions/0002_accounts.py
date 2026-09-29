"""AUTH-001: accounts, identities, password credentials and durable sessions.

Revision: 0002_accounts; parent: 0001. No user or staff is seeded.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_accounts"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("accounts",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("public_code", sa.String(16), unique=True, nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("state IN ('active','generation_suspended','security_locked','deletion_pending','deleted')", name="account_state"))
    op.create_table("auth_identities",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(254), nullable=False),
        sa.Column("verified_at", sa.BigInteger),
        sa.UniqueConstraint("provider", "subject", name="identity_subject"),
        sa.UniqueConstraint("account_id", "provider", name="account_identity_provider"))
    op.create_table("password_credentials",
        sa.Column("identity_id", sa.Uuid, sa.ForeignKey("auth_identities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("password_hash", sa.String(256), nullable=False))
    op.create_table("account_sessions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("csrf_token", sa.String(43), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("last_seen_at", sa.BigInteger, nullable=False),
        sa.Column("expires_at", sa.BigInteger, nullable=False),
        sa.Column("idle_seconds", sa.Integer, nullable=False),
        sa.Column("revoked_at", sa.BigInteger),
        sa.Column("client_label", sa.String(160), nullable=False),
        sa.CheckConstraint("expires_at > created_at AND idle_seconds > 0", name="session_lifetime"))
    op.create_table("account_invites",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("expires_at", sa.BigInteger, nullable=False),
        sa.Column("consumed_at", sa.BigInteger),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.CheckConstraint("expires_at > created_at", name="invite_lifetime"))
    op.create_table("auth_rate_limits",
        sa.Column("bucket_key", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.BigInteger, primary_key=True),
        sa.Column("count", sa.Integer, nullable=False),
        sa.CheckConstraint("count > 0", name="rate_positive"))
    op.create_table("account_permissions",
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission", sa.String(80), primary_key=True),
        sa.Column("expires_at", sa.BigInteger))
    op.create_table("account_audit",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_id", sa.Uuid),
        sa.Column("created_at", sa.BigInteger, nullable=False))
    op.create_index("ix_auth_identities_account_id", "auth_identities", ["account_id"])
    op.create_index("ix_account_sessions_account_id", "account_sessions", ["account_id"])


def downgrade() -> None:
    op.drop_table("account_audit")
    op.drop_table("account_permissions")
    op.drop_table("auth_rate_limits")
    op.drop_table("account_invites")
    op.drop_table("account_sessions")
    op.drop_table("password_credentials")
    op.drop_table("auth_identities")
    op.drop_table("accounts")
