"""ADMIN-001: finite staff grant policy and append-only administrative events."""
from alembic import op
import sqlalchemy as sa

revision = "0006_admin"
down_revision = "0005_entitlements"
branch_labels = depends_on = None


def upgrade():
    op.create_table("admin_grant_policies",
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), primary_key=True),
        sa.Column("max_grant", sa.BigInteger, nullable=False),
        sa.Column("expires_at", sa.BigInteger),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("max_grant >= 0 AND max_grant <= 1000000000", name="admin_grant_bound"))
    op.create_table("admin_events",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("target_id", sa.Uuid),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("case_reference", sa.String(64)),
        sa.Column("operation_id", sa.Uuid, unique=True),
        sa.Column("entry_id", sa.Uuid),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("outcome IN ('success','denied')", name="admin_event_outcome"))
    op.create_index("ix_admin_events_actor_id", "admin_events", ["actor_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION reject_admin_event_change() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'administrative events are append only'; END; $$""")
        op.execute("""CREATE TRIGGER immutable_admin_events BEFORE UPDATE OR DELETE OR TRUNCATE ON admin_events
            FOR EACH STATEMENT EXECUTE FUNCTION reject_admin_event_change()""")


def downgrade():
    raise RuntimeError("Administrative audit is retained; use a reviewed forward migration")
