"""ACCESS-001 grant provenance, local delegation ceilings and immutable operation identity."""
import sqlalchemy as sa
from ..accounts.admin_access import metadata


grants = sa.Table("staff_access_grants", metadata,
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("permission", sa.String(80), primary_key=True),
    sa.Column("scope", sa.String(32), nullable=False),
    sa.Column("granted_by", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="SET NULL")),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger),
    sa.CheckConstraint("scope = 'global'", name="staff_access_scope"),
    sa.CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="staff_access_expiry"))

ceilings = sa.Table("staff_delegation_ceiling", metadata,
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("permission", sa.String(80), primary_key=True),
    sa.Column("scope", sa.String(32), nullable=False),
    sa.Column("granted_by", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="SET NULL")),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger),
    sa.CheckConstraint("scope = 'global'", name="staff_ceiling_scope"),
    sa.CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="staff_ceiling_expiry"))

operations = sa.Table("staff_access_operations", metadata,
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

sa.Index("ix_staff_access_permission", grants.c.permission, grants.c.expires_at)
sa.Index("ix_staff_ceiling_permission", ceilings.c.permission, ceilings.c.expires_at)

state = sa.Table("staff_access_state", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("version", sa.Integer, nullable=False),
    sa.CheckConstraint("id = 1", name="staff_access_singleton"),
    sa.CheckConstraint("version >= 0", name="staff_access_version_nonnegative"))

TABLES = (state, grants, ceilings, operations)
