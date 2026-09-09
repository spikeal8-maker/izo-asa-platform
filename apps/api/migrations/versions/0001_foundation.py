"""Foundation marker only; user/job/ledger tables belong to the next slice."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("platform_metadata", sa.Column("key", sa.String(80), primary_key=True),
                    sa.Column("value", sa.Text(), nullable=False))


def downgrade() -> None:
    op.drop_table("platform_metadata")
