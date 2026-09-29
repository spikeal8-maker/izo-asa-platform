"""API-001: durable external provider request identity and cost metadata.

Frozen schema snapshot; never import mutable application models here.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_provider_calls"
down_revision = "0008_jobs"
branch_labels = depends_on = None

metadata = sa.MetaData()
sa.Table("generation_jobs", metadata, sa.Column("id", sa.Uuid, primary_key=True))
provider_calls = sa.Table("generation_provider_calls", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("job_id", sa.Uuid, sa.ForeignKey("generation_jobs.id"), nullable=False, unique=True),
    sa.Column("provider", sa.String(32), nullable=False),
    sa.Column("connection_id", sa.String(80), nullable=False),
    sa.Column("credential_ref", sa.String(120), nullable=False),
    sa.Column("provider_request_id", sa.String(180)),
    sa.Column("status_url", sa.String(500)),
    sa.Column("response_url", sa.String(500)),
    sa.Column("cancel_url", sa.String(500)),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("estimated_cost_microusd", sa.BigInteger),
    sa.Column("reported_cost_microusd", sa.BigInteger),
    sa.Column("last_error_code", sa.String(80)),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("provider", "connection_id", "provider_request_id", name="provider_request_scope"),
    sa.CheckConstraint("state IN ('submitting','accepted','running','completed','failed','cancel_requested','cancelled','submission_unknown')", name="provider_call_state"),
    sa.CheckConstraint("estimated_cost_microusd IS NULL OR estimated_cost_microusd >= 0", name="provider_estimate_nonnegative"),
    sa.CheckConstraint("reported_cost_microusd IS NULL OR reported_cost_microusd >= 0", name="provider_reported_nonnegative"))
sa.Index("ix_provider_calls_state", provider_calls.c.provider, provider_calls.c.state, provider_calls.c.updated_at)


def upgrade():
    conn = op.get_bind()
    provider_calls.create(conn)


def downgrade():
    raise RuntimeError("Provider request identity may represent paid work; use a reviewed forward migration")
