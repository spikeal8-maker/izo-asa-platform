"""GUEST-001: isolated guest sessions and auditable one-time trial credits."""
from alembic import op
import sqlalchemy as sa

revision = "0011_guest"
down_revision = "0010_access"
branch_labels = depends_on = None


TRIAL_MOVEMENT = """(kind = 'trial' AND balance_delta > 0 AND balance_delta <= 3
    AND reserved_delta = 0 AND reservation_id IS NULL AND case_id IS NULL AND actor_id IS NULL)
 OR (kind = 'grant' AND balance_delta > 0 AND balance_delta <= 1000000000
    AND reserved_delta = 0 AND reservation_id IS NULL AND case_id IS NOT NULL AND actor_id IS NOT NULL)
 OR (kind = 'reserve' AND balance_delta = 0 AND reserved_delta > 0 AND reserved_delta <= 1000000000
    AND reservation_id IS NOT NULL AND case_id IS NULL AND actor_id IS NULL)
 OR (kind = 'settle' AND balance_delta <= 0 AND reserved_delta < 0 AND balance_delta >= reserved_delta
    AND reservation_id IS NOT NULL AND case_id IS NULL AND actor_id IS NULL)
 OR (kind = 'release' AND balance_delta = 0 AND reserved_delta < 0
    AND reservation_id IS NOT NULL AND case_id IS NULL AND actor_id IS NULL)"""

TRIAL_REASON = """(kind = 'trial' AND reason = 'guest_trial')
 OR (kind = 'grant' AND reason IN ('compensation','test_grant'))
 OR (kind NOT IN ('trial','grant') AND reason = 'generation')"""


def upgrade():
    op.create_table("guest_sessions",
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
        sa.CheckConstraint("claimed_at IS NULL OR claimed_at >= created_at", name="guest_claim_time"))
    op.create_index("ix_guest_session_expiry", "guest_sessions", ["expires_at"])
    op.drop_constraint("credit_entry_movement", "credit_ledger", type_="check")
    op.drop_constraint("credit_entry_reason", "credit_ledger", type_="check")
    op.create_check_constraint("credit_entry_movement", "credit_ledger", TRIAL_MOVEMENT)
    op.create_check_constraint("credit_entry_reason", "credit_ledger", TRIAL_REASON)


def downgrade():
    raise RuntimeError("Guest claims and trial-credit audit are retained; use a reviewed forward migration")
