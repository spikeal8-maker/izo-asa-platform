"""Integer credits, immutable ledger and reservation lifecycle. No user balances imported."""
from alembic import op
import sqlalchemy as sa

revision = "0004_credits"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("credit_wallets",
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), primary_key=True),
        sa.Column("balance", sa.BigInteger, nullable=False),
        sa.Column("reserved", sa.BigInteger, nullable=False),
        sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.CheckConstraint("balance >= 0 AND balance <= 9000000000000 AND reserved >= 0 AND reserved <= balance AND sequence >= 0", name="credit_wallet_bounds"))
    op.create_table("credit_reservations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("credit_wallets.account_id"), nullable=False),
        sa.Column("request_id", sa.Uuid, unique=True, nullable=False),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("charged", sa.BigInteger),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("closed_at", sa.BigInteger),
        sa.UniqueConstraint("account_id", "id", name="credit_reservation_owner"),
        sa.CheckConstraint("amount > 0 AND amount <= 1000000000", name="credit_reservation_amount"),
        sa.CheckConstraint("(state = 'active' AND charged IS NULL AND closed_at IS NULL) OR (state = 'settled' AND charged IS NOT NULL AND charged >= 0 AND charged <= amount AND closed_at IS NOT NULL) OR (state = 'released' AND charged IS NOT NULL AND charged = 0 AND closed_at IS NOT NULL)", name="credit_reservation_state"))
    op.create_index("ix_credit_reservation_owner_state", "credit_reservations", ["account_id", "state"])
    op.create_table("credit_ledger",
        sa.Column("entry_id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("credit_wallets.account_id"), nullable=False),
        sa.Column("operation_id", sa.Uuid, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("balance_delta", sa.BigInteger, nullable=False),
        sa.Column("reserved_delta", sa.BigInteger, nullable=False),
        sa.Column("balance_after", sa.BigInteger, nullable=False),
        sa.Column("reserved_after", sa.BigInteger, nullable=False),
        sa.Column("reservation_id", sa.Uuid),
        sa.Column("case_id", sa.Uuid),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("accounts.id")),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("account_id", "operation_id", name="credit_operation_once"),
        sa.UniqueConstraint("account_id", "sequence", name="credit_sequence_once"),
        sa.UniqueConstraint("case_id", name="credit_case_once"),
        sa.ForeignKeyConstraint(["account_id", "reservation_id"],
            ["credit_reservations.account_id", "credit_reservations.id"]),
        sa.CheckConstraint("sequence > 0 AND balance_after >= 0 AND balance_after <= 9000000000000 AND reserved_after >= 0 AND reserved_after <= balance_after", name="credit_entry_bounds"),
        sa.CheckConstraint("(kind = 'grant' AND balance_delta > 0 AND balance_delta <= 1000000000 AND reserved_delta = 0 AND reservation_id IS NULL AND case_id IS NOT NULL AND actor_id IS NOT NULL) OR (kind = 'reserve' AND balance_delta = 0 AND reserved_delta > 0 AND reserved_delta <= 1000000000 AND reservation_id IS NOT NULL AND case_id IS NULL AND actor_id IS NULL) OR (kind = 'settle' AND balance_delta <= 0 AND reserved_delta < 0 AND balance_delta >= reserved_delta AND reservation_id IS NOT NULL AND case_id IS NULL AND actor_id IS NULL) OR (kind = 'release' AND balance_delta = 0 AND reserved_delta < 0 AND reservation_id IS NOT NULL AND case_id IS NULL AND actor_id IS NULL)", name="credit_entry_movement"),
        sa.CheckConstraint("(kind = 'grant' AND reason IN ('compensation','test_grant')) OR (kind <> 'grant' AND reason = 'generation')", name="credit_entry_reason"))

    # PostgreSQL runtime guard. DB administrators can bypass triggers: not a claim
    # of tamper-proof storage against the database owner.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION credit_ledger_immutable() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'credit_ledger_is_immutable' USING ERRCODE = '23514';
            END; $$""")
        op.execute("""CREATE TRIGGER credit_ledger_no_change
            BEFORE UPDATE OR DELETE ON credit_ledger FOR EACH ROW
            EXECUTE FUNCTION credit_ledger_immutable()""")
        op.execute("""CREATE TRIGGER credit_ledger_no_truncate
            BEFORE TRUNCATE ON credit_ledger FOR EACH STATEMENT
            EXECUTE FUNCTION credit_ledger_immutable()""")


def downgrade() -> None:
    # Migration rollback must not silently erase a populated financial journal.
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM credit_ledger)" )).scalar():
        raise RuntimeError("Refusing to drop a populated credit ledger")
    op.drop_table("credit_ledger")
    op.drop_index("ix_credit_reservation_owner_state", table_name="credit_reservations")
    op.drop_table("credit_reservations")
    op.drop_table("credit_wallets")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION credit_ledger_immutable()")
