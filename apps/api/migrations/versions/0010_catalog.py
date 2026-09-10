"""CATALOG-001: versioned capability/connection metadata and non-secret credential bindings.

Revision: 0010_catalog
Parent: 0009_provider_execution
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_catalog"
down_revision = "0009_provider_execution"
branch_labels = depends_on = None


def upgrade():
    op.create_table("catalog_capability_revisions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("capability_id", sa.String(80), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("content_json", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("capability_id", "revision", name="catalog_capability_revision_unique"),
        sa.CheckConstraint("revision > 0", name="catalog_capability_revision_positive"))
    op.create_table("catalog_capability_heads",
        sa.Column("capability_id", sa.String(80), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("draft_revision_id", sa.Uuid, sa.ForeignKey("catalog_capability_revisions.id", ondelete="RESTRICT")),
        sa.Column("published_revision_id", sa.Uuid, sa.ForeignKey("catalog_capability_revisions.id", ondelete="RESTRICT")),
        sa.CheckConstraint("version >= 0", name="catalog_capability_head_version"))
    op.create_table("catalog_connection_revisions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("connection_id", sa.String(80), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("content_json", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("connection_id", "revision", name="catalog_connection_revision_unique"),
        sa.CheckConstraint("revision > 0", name="catalog_connection_revision_positive"))
    op.create_table("catalog_connection_heads",
        sa.Column("connection_id", sa.String(80), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("draft_revision_id", sa.Uuid, sa.ForeignKey("catalog_connection_revisions.id", ondelete="RESTRICT")),
        sa.Column("published_revision_id", sa.Uuid, sa.ForeignKey("catalog_connection_revisions.id", ondelete="RESTRICT")),
        sa.Column("runtime_state", sa.String(16), nullable=False, server_default="disabled"),
        sa.CheckConstraint("version >= 0", name="catalog_connection_head_version"),
        sa.CheckConstraint("runtime_state = 'disabled'", name="catalog_connection_runtime_disabled"))
    op.create_table("catalog_credential_bindings",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("connection_id", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("source_type", sa.String(24), nullable=False),
        sa.Column("secret_ref", sa.String(200), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("account_ref", sa.String(120), nullable=False),
        sa.Column("project_ref", sa.String(120)),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("revoked_at", sa.BigInteger),
        sa.UniqueConstraint("connection_id", "version", name="catalog_credential_version_unique"),
        sa.CheckConstraint("source_type IN ('env','secret_file','secret_manager')", name="catalog_credential_source"),
        sa.CheckConstraint("environment IN ('development','test')", name="catalog_credential_environment"))
    op.create_index("ix_catalog_credential_connection", "catalog_credential_bindings", ["connection_id", "version"])
    op.create_table("catalog_contract_proofs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("capability_id", sa.String(80), nullable=False),
        sa.Column("connection_id", sa.String(80), nullable=False),
        sa.Column("capability_hash", sa.String(64), nullable=False),
        sa.Column("connection_hash", sa.String(64), nullable=False),
        sa.Column("credential_version", sa.Integer, nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("credential_version > 0", name="catalog_proof_credential_positive"))
    op.create_table("catalog_changes",
        sa.Column("operation_id", sa.Uuid, primary_key=True),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("target", sa.String(100), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("result_version", sa.Integer, nullable=False),
        sa.Column("result_id", sa.Uuid),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("result_version >= 0", name="catalog_change_version"))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION catalog_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'immutable catalog history' USING ERRCODE = '55000'; END $$""")
        for name in ("catalog_capability_revisions", "catalog_connection_revisions", "catalog_contract_proofs", "catalog_changes"):
            op.execute(f"CREATE TRIGGER {name}_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON {name} "
                       "FOR EACH STATEMENT EXECUTE FUNCTION catalog_immutable()")


def downgrade():
    conn = op.get_bind()
    for name in ("catalog_capability_revisions", "catalog_connection_revisions", "catalog_credential_bindings", "catalog_contract_proofs", "catalog_changes"):
        if conn.execute(sa.text(f"SELECT COUNT(*) FROM {name}")).scalar_one():
            raise RuntimeError("Populated catalog downgrade is forbidden")
    for name in ("catalog_changes", "catalog_contract_proofs", "catalog_credential_bindings",
                 "catalog_connection_heads", "catalog_connection_revisions",
                 "catalog_capability_heads", "catalog_capability_revisions"):
        op.drop_table(name)
    if conn.dialect.name == "postgresql":
        op.execute("DROP FUNCTION catalog_immutable()")
