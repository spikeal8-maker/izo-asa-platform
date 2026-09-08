"""One-use email proofs and secret-free TEST delivery intents. No live sender."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("account_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE")),
        sa.Column("identity_id", sa.Uuid(), sa.ForeignKey("auth_identities.id", ondelete="CASCADE")),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("binding_hash", sa.String(64)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("consumed_at", sa.BigInteger()),
        sa.Column("cancelled_at", sa.BigInteger()),
        sa.CheckConstraint("purpose IN ('verify_email','reset_password')", name="challenge_purpose"),
        sa.CheckConstraint("expires_at > created_at AND attempts >= 0", name="challenge_bounds"),
        sa.CheckConstraint("(account_id IS NULL AND identity_id IS NULL AND binding_hash IS NULL) OR "
                           "(account_id IS NOT NULL AND identity_id IS NOT NULL AND binding_hash IS NOT NULL)",
                           name="challenge_binding"))
    op.create_index("ix_account_challenges_account_id", "account_challenges", ["account_id"])
    op.create_index("ix_account_challenges_expires_at", "account_challenges", ["expires_at"])
    op.create_table("account_test_mail",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE")),
        sa.Column("identity_id", sa.Uuid(), sa.ForeignKey("auth_identities.id", ondelete="CASCADE")),
        sa.Column("challenge_id", sa.Uuid(), sa.ForeignKey("account_challenges.id", ondelete="CASCADE"), unique=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("kind IN ('verify_email','reset_password','password_changed')", name="test_mail_kind"))
    op.create_index("ix_account_test_mail_account_id", "account_test_mail", ["account_id"])


def downgrade() -> None:
    op.drop_table("account_test_mail")
    op.drop_table("account_challenges")
