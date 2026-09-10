"""CATALOG-001 immutable revisions/proofs plus small mutable head/binding state."""
import sqlalchemy as sa
from ..accounts.tables import metadata

capability_revisions = sa.Table("catalog_capability_revisions", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("capability_id", sa.String(80), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("content_json", sa.Text, nullable=False),
    sa.Column("content_hash", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("capability_id", "revision", name="catalog_capability_revision_unique"),
    sa.CheckConstraint("revision > 0", name="catalog_capability_revision_positive"))

capability_heads = sa.Table("catalog_capability_heads", metadata,
    sa.Column("capability_id", sa.String(80), primary_key=True),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("draft_revision_id", sa.Uuid, sa.ForeignKey("catalog_capability_revisions.id", ondelete="RESTRICT")),
    sa.Column("published_revision_id", sa.Uuid, sa.ForeignKey("catalog_capability_revisions.id", ondelete="RESTRICT")),
    sa.CheckConstraint("version >= 0", name="catalog_capability_head_version"))

connection_revisions = sa.Table("catalog_connection_revisions", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("connection_id", sa.String(80), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("content_json", sa.Text, nullable=False),
    sa.Column("content_hash", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("connection_id", "revision", name="catalog_connection_revision_unique"),
    sa.CheckConstraint("revision > 0", name="catalog_connection_revision_positive"))

connection_heads = sa.Table("catalog_connection_heads", metadata,
    sa.Column("connection_id", sa.String(80), primary_key=True),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("draft_revision_id", sa.Uuid, sa.ForeignKey("catalog_connection_revisions.id", ondelete="RESTRICT")),
    sa.Column("published_revision_id", sa.Uuid, sa.ForeignKey("catalog_connection_revisions.id", ondelete="RESTRICT")),
    sa.Column("runtime_state", sa.String(16), nullable=False, server_default="disabled"),
    sa.CheckConstraint("version >= 0", name="catalog_connection_head_version"),
    sa.CheckConstraint("runtime_state = 'disabled'", name="catalog_connection_runtime_disabled"))

credential_bindings = sa.Table("catalog_credential_bindings", metadata,
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
sa.Index("ix_catalog_credential_connection", credential_bindings.c.connection_id, credential_bindings.c.version)

proofs = sa.Table("catalog_contract_proofs", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("capability_id", sa.String(80), nullable=False),
    sa.Column("connection_id", sa.String(80), nullable=False),
    sa.Column("capability_hash", sa.String(64), nullable=False),
    sa.Column("connection_hash", sa.String(64), nullable=False),
    sa.Column("credential_version", sa.Integer, nullable=False),
    sa.Column("evidence_hash", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("credential_version > 0", name="catalog_proof_credential_positive"))

changes = sa.Table("catalog_changes", metadata,
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

TABLES = (capability_revisions, capability_heads, connection_revisions, connection_heads,
          credential_bindings, proofs, changes)
