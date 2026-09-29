"""Immutable plan versions, one default pointer and account assignments."""
from alembic import op
import sqlalchemy as sa

revision = "0005_entitlements"
down_revision = "0004_credits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("entitlement_revisions",
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("plan_code", sa.String(16), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("policy_json", sa.Text, nullable=False),
    sa.Column("policy_hash", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("plan_code", "revision", name="entitlement_revision_unique"),
    sa.CheckConstraint("plan_code IN ('basic','extended','custom')", name="entitlement_plan_code"),
    sa.CheckConstraint("revision > 0", name="entitlement_revision_positive"))
    op.create_table("entitlement_default",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("revision_id", sa.Uuid, sa.ForeignKey("entitlement_revisions.id")),
    sa.Column("version", sa.Integer, nullable=False),
    sa.CheckConstraint("id = 1 AND version >= 0", name="entitlement_single_default"))
    op.create_table("entitlement_assignments",
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="RESTRICT"), primary_key=True),
    sa.Column("revision_id", sa.Uuid, sa.ForeignKey("entitlement_revisions.id")),
    sa.Column("starts_at", sa.BigInteger),
    sa.Column("expires_at", sa.BigInteger),
    sa.Column("version", sa.Integer, nullable=False),
    sa.CheckConstraint("version > 0", name="entitlement_assignment_version"),
    sa.CheckConstraint("(revision_id IS NULL AND starts_at IS NULL AND expires_at IS NULL) OR "
        "(revision_id IS NOT NULL AND starts_at IS NOT NULL AND starts_at >= 0 AND "
        "(expires_at IS NULL OR expires_at > starts_at))", name="entitlement_assignment_period"))
    op.create_table("entitlement_changes",
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
    op.get_bind().execute(sa.text("INSERT INTO entitlement_default (id, version) VALUES (1, 0)"))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION entitlement_immutable() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'immutable entitlement history' USING ERRCODE = '55000';
            END $$""")
        for name in ("entitlement_revisions", "entitlement_changes"):
            op.execute(f"CREATE TRIGGER {name}_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON {name} "
                       "FOR EACH STATEMENT EXECUTE FUNCTION entitlement_immutable()")


def downgrade() -> None:
    conn = op.get_bind()
    # Never discard published plans/assignments/history during rollback.
    for name in ("entitlement_revisions", "entitlement_assignments", "entitlement_changes"):
        if conn.execute(sa.text(f"SELECT COUNT(*) FROM {name}")).scalar_one():
            raise RuntimeError("Populated entitlement downgrade is forbidden")
    for name in ("entitlement_changes", "entitlement_assignments", "entitlement_default", "entitlement_revisions"):
        op.drop_table(name)
    if conn.dialect.name == "postgresql":
        op.execute("DROP FUNCTION entitlement_immutable()")
