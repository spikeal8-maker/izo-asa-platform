"""Persist explicit user choice independently of automatic thread titles."""
import sqlalchemy as sa
from alembic import op

revision = "0017_chat_manual_title"
down_revision = "0016_chat_thread_created_index"
branch_labels = depends_on = None


def upgrade():
    op.add_column("chat_threads", sa.Column(
        "title_is_manual", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade():
    raise RuntimeError("Manual thread titles are retained; use a reviewed forward migration")
