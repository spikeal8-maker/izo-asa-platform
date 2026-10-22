"""Explicit account-scoped shadow binding for test-only platform Chat requests."""
from alembic import op
import sqlalchemy as sa

revision = "0022_platform_chat_fake_demo"
down_revision = "0021_platform_chat_registry"
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint("chat_connection_bounds", "chat_connections", type_="check")
    op.create_check_constraint("chat_connection_bounds", "chat_connections",
        "provider IN ('deepseek','openrouter','platform-deepseek') "
        "AND generation > 0 AND revision > 0")
    op.create_table("platform_chat_daily_usage",
        sa.Column("provider", sa.String(24), primary_key=True),
        sa.Column("day_start", sa.BigInteger, primary_key=True),
        sa.Column("requests_admitted", sa.Integer, nullable=False),
        sa.Column("confirmed_cost_microusd", sa.BigInteger, nullable=False, server_default="0"),
        sa.CheckConstraint("requests_admitted >= 0 AND requests_admitted <= 200",
                           name="platform_daily_count_bounds"),
        sa.CheckConstraint("confirmed_cost_microusd >= 0", name="platform_daily_cost_bounds"))


def downgrade():
    raise RuntimeError("Retain admitted Chat requests and platform daily quota evidence")
