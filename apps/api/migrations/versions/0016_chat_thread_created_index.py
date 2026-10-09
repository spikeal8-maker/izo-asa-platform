"""Index immutable account-owned thread history ordering."""
from alembic import op

revision = "0016_chat_thread_created_index"
down_revision = "0015_chat_vision"
branch_labels = depends_on = None


def upgrade():
    op.create_index("ix_chat_threads_owner_created", "chat_threads",
                    ["account_id", "created_at", "id"])


def downgrade():
    raise RuntimeError("Chat history index is retained; use a reviewed forward migration")
