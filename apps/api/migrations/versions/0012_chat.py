"""CHAT-DEEPSEEK-001: account credential and durable text conversation state."""
from alembic import op
import sqlalchemy as sa

revision = "0012_chat"
down_revision = "0011_guest"
branch_labels = depends_on = None

def upgrade():
    op.create_table("chat_connections",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("generation", sa.Integer, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("nonce", sa.LargeBinary, nullable=False),
        sa.Column("ciphertext", sa.LargeBinary, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("verified_at", sa.BigInteger),
        sa.Column("last_operation_id", sa.Uuid, nullable=False),
        sa.Column("last_operation_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("id", "account_id", name="chat_connection_owner"),
        sa.CheckConstraint("provider = 'deepseek' AND generation > 0 AND revision > 0",
                           name="chat_connection_bounds"))

    op.create_table("chat_threads",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("next_sequence", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("next_sequence >= 1", name="chat_thread_sequence"))
    op.create_index("ix_chat_threads_owner_time", "chat_threads",
                    ["account_id", "updated_at", "id"])

    op.create_table("chat_requests",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("thread_id", sa.Uuid, sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("model_revision", sa.String(64), nullable=False),
        sa.Column("connection_id", sa.Uuid, nullable=False),
        sa.Column("credential_generation", sa.Integer, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("stop_requested_at", sa.BigInteger),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.BigInteger, nullable=False),
        sa.Column("deadline_at", sa.BigInteger, nullable=False),
        sa.ForeignKeyConstraint(["connection_id", "account_id"],
                                ["chat_connections.id", "chat_connections.account_id"]),
        sa.UniqueConstraint("id", "account_id", name="chat_request_owner"),
        sa.CheckConstraint("credential_generation > 0", name="chat_request_generation"),
        sa.CheckConstraint(
            "state IN ('pending','streaming','completed','interrupted','error','stopped')",
            name="chat_request_state"))
    op.create_index("ix_chat_requests_owner_time", "chat_requests",
                    ["account_id", "created_at", "id"])
    op.create_index("ix_chat_one_active_per_thread", "chat_requests", ["thread_id"],
                    unique=True,
                    postgresql_where=sa.text("state IN ('pending','streaming')"))

    op.create_table("chat_messages",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("thread_id", sa.Uuid, sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("request_id", sa.Uuid, sa.ForeignKey("chat_requests.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.Column("part_version", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("thread_id", "sequence", name="chat_message_sequence"),
        sa.UniqueConstraint("request_id", "role", name="chat_request_role_once"),
        sa.CheckConstraint(
            "role IN ('user','assistant') AND sequence > 0 AND part_version = 1",
            name="chat_message_shape"),
        sa.CheckConstraint(
            "state IN ('complete','partial','interrupted','error','stopped')",
            name="chat_message_state"))

    op.create_table("chat_rate_limits",
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("window_start", sa.BigInteger, primary_key=True),
        sa.Column("count", sa.Integer, nullable=False),
        sa.CheckConstraint(
            "kind IN ('request','credential') AND count > 0",
            name="chat_rate_shape"))

def downgrade():
    raise RuntimeError("Chat credentials and conversation history are retained; use a reviewed forward migration")
