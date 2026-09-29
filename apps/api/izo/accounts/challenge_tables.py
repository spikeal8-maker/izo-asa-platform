"""Metadata for one-use proofs and secret-free test delivery intents."""
import sqlalchemy as sa
from .tables import metadata

challenges = sa.Table("account_challenges", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), index=True),
    sa.Column("identity_id", sa.Uuid, sa.ForeignKey("auth_identities.id", ondelete="CASCADE")),
    sa.Column("purpose", sa.String(24), nullable=False),
    sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
    sa.Column("binding_hash", sa.String(64)),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
    sa.Column("consumed_at", sa.BigInteger),
    sa.Column("cancelled_at", sa.BigInteger),
    sa.CheckConstraint("purpose IN ('verify_email','reset_password')", name="challenge_purpose"),
    sa.CheckConstraint("expires_at > created_at AND attempts >= 0", name="challenge_bounds"),
    sa.CheckConstraint("(account_id IS NULL AND identity_id IS NULL AND binding_hash IS NULL) OR "
                       "(account_id IS NOT NULL AND identity_id IS NOT NULL AND binding_hash IS NOT NULL)",
                       name="challenge_binding"))
mail = sa.Table("account_test_mail", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), index=True),
    sa.Column("identity_id", sa.Uuid, sa.ForeignKey("auth_identities.id", ondelete="CASCADE")),
    sa.Column("challenge_id", sa.Uuid, sa.ForeignKey("account_challenges.id", ondelete="CASCADE"), unique=True),
    sa.Column("kind", sa.String(24), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("kind IN ('verify_email','reset_password','password_changed')", name="test_mail_kind"))
