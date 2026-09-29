"""ACCESS-001: staff delegation provenance, ceilings and immutable operation receipts."""
from alembic import op
import sqlalchemy as sa

revision = "0010_access"
down_revision = "0009_provider_calls"
branch_labels = depends_on = None


def upgrade():
    op.create_table("staff_access_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.CheckConstraint("id = 1", name="staff_access_singleton"),
        sa.CheckConstraint("version >= 0", name="staff_access_version_nonnegative"))
    op.execute("INSERT INTO staff_access_state (id, version) VALUES (1, 0)")
    op.create_table("staff_access_grants",
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission", sa.String(80), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("granted_by", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("expires_at", sa.BigInteger),
        sa.CheckConstraint("scope = 'global'", name="staff_access_scope"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="staff_access_expiry"))
    op.create_table("staff_delegation_ceiling",
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission", sa.String(80), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("granted_by", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("expires_at", sa.BigInteger),
        sa.CheckConstraint("scope = 'global'", name="staff_ceiling_scope"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="staff_ceiling_expiry"))
    op.create_table("staff_access_operations",
        sa.Column("operation_id", sa.Uuid, primary_key=True),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("target_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("permission", sa.String(80), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.BigInteger),
        sa.Column("case_reference", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("action IN ('grant','revoke')", name="staff_access_action"),
        sa.CheckConstraint("scope = 'global'", name="staff_operation_scope"))
    op.create_index("ix_staff_access_permission", "staff_access_grants", ["permission", "expires_at"])
    op.create_index("ix_staff_ceiling_permission", "staff_delegation_ceiling", ["permission", "expires_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION reject_staff_access_operation_change() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'staff access operations are append only'; END; $$""")
        op.execute("""CREATE TRIGGER immutable_staff_access_operations BEFORE UPDATE OR DELETE OR TRUNCATE
            ON staff_access_operations FOR EACH STATEMENT EXECUTE FUNCTION reject_staff_access_operation_change()""")


def downgrade():
    raise RuntimeError("Staff access provenance is retained; use a reviewed forward migration")
