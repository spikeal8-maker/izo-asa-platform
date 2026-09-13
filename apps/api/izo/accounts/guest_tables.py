"""Accounts-owned guest bearer sessions, separate from normal account sessions."""
import sqlalchemy as sa

from .tables import metadata

sessions = sa.Table(
    "guest_sessions", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"),
              unique=True, nullable=False),
    sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
    sa.Column("csrf_token", sa.String(43), nullable=False),
    sa.Column("network_key", sa.String(64), nullable=False),
    sa.Column("trial_operation_id", sa.Uuid),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("last_seen_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False),
    sa.Column("claimed_at", sa.BigInteger),
    sa.CheckConstraint("expires_at > created_at", name="guest_session_lifetime"),
    sa.CheckConstraint("claimed_at IS NULL OR claimed_at >= created_at", name="guest_claim_time"),
)
sa.Index("ix_guest_session_expiry", sessions.c.expires_at)
