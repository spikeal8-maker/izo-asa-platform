"""Allow one account-owned Chat credential per supported provider."""
from alembic import op

revision = "0014_chat_multi_provider"
down_revision = "0013_admin_catalog"
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint(
        "chat_connections_account_id_key", "chat_connections", type_="unique")
    op.drop_constraint(
        "chat_connection_bounds", "chat_connections", type_="check")
    op.create_unique_constraint(
        "chat_connection_account_provider", "chat_connections",
        ["account_id", "provider"])
    op.create_check_constraint(
        "chat_connection_bounds", "chat_connections",
        "provider IN ('deepseek','openrouter') AND generation > 0 AND revision > 0")


def downgrade():
    raise RuntimeError(
        "Multi-provider credentials are retained; use a reviewed forward migration")
