"""API-001: immutable provider execution snapshot and diagnostic provider receipt.

Revision: 0009_provider_execution
Parent: 0008_jobs
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_provider_execution"
down_revision = "0008_jobs"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("job_quotes") as batch:
        batch.add_column(sa.Column("execution_json", sa.Text(), nullable=True))
    with op.batch_alter_table("generation_jobs") as batch:
        batch.add_column(sa.Column("execution_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("provider_ref", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("provider_cost_usd", sa.Numeric(14, 6), nullable=True))


def downgrade():
    raise RuntimeError("Provider execution snapshots are audit data; use a reviewed forward migration")
