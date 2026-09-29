"""Relational metadata only; migration owns schema creation."""
import sqlalchemy as sa
from ..accounts.entitlement_access import metadata

revisions = sa.Table("entitlement_revisions", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("plan_code", sa.String(16), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("policy_json", sa.Text, nullable=False),
    sa.Column("policy_hash", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("plan_code", "revision", name="entitlement_revision_unique"),
    sa.CheckConstraint("plan_code IN ('basic','extended','custom')", name="entitlement_plan_code"),
    sa.CheckConstraint("revision > 0", name="entitlement_revision_positive"))
defaults = sa.Table("entitlement_default", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("revision_id", sa.Uuid, sa.ForeignKey("entitlement_revisions.id")),
    sa.Column("version", sa.Integer, nullable=False),
    sa.CheckConstraint("id = 1 AND version >= 0", name="entitlement_single_default"))
assignments = sa.Table("entitlement_assignments", metadata,
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="RESTRICT"), primary_key=True),
    sa.Column("revision_id", sa.Uuid, sa.ForeignKey("entitlement_revisions.id")),
    sa.Column("starts_at", sa.BigInteger),
    sa.Column("expires_at", sa.BigInteger),
    sa.Column("version", sa.Integer, nullable=False),
    sa.CheckConstraint("version > 0", name="entitlement_assignment_version"),
    sa.CheckConstraint("(revision_id IS NULL AND starts_at IS NULL AND expires_at IS NULL) OR "
        "(revision_id IS NOT NULL AND starts_at IS NOT NULL AND starts_at >= 0 AND "
        "(expires_at IS NULL OR expires_at > starts_at))", name="entitlement_assignment_period"))
changes = sa.Table("entitlement_changes", metadata,
    sa.Column("operation_id", sa.Uuid, primary_key=True),
    sa.Column("actor_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
    sa.Column("target_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="RESTRICT")),
    sa.Column("action", sa.String(16), nullable=False),
    sa.Column("revision_id", sa.Uuid, sa.ForeignKey("entitlement_revisions.id")),
    sa.Column("fingerprint", sa.String(64), nullable=False),
    sa.Column("reason", sa.String(500), nullable=False),
    sa.Column("result_version", sa.Integer, nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("action IN ('publish','default','assign')", name="entitlement_change_action"),
    sa.CheckConstraint("result_version > 0", name="entitlement_change_version"))
