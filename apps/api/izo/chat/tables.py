"""Chat relational schema; account and Media ownership stay server-side."""
import sqlalchemy as sa

metadata = sa.MetaData()
sa.Table("accounts", metadata, sa.Column("id", sa.Uuid, primary_key=True))

media_assets = sa.Table(
    "media_assets", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, nullable=False),
    sa.Column("object_key", sa.String(200), nullable=False),
    sa.Column("sha256", sa.String(64), nullable=False),
    sa.Column("byte_size", sa.BigInteger, nullable=False),
    sa.Column("width", sa.Integer, nullable=False),
    sa.Column("height", sa.Integer, nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
)

connections = sa.Table(
    "chat_connections", metadata,
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
                       name="chat_connection_bounds"),
)

threads = sa.Table(
    "chat_threads", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("title", sa.String(120), nullable=False),
    sa.Column("next_sequence", sa.BigInteger, nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("next_sequence >= 1", name="chat_thread_sequence"),
)
sa.Index("ix_chat_threads_owner_time", threads.c.account_id, threads.c.updated_at, threads.c.id)

requests = sa.Table(
    "chat_requests", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("thread_id", sa.Uuid, sa.ForeignKey(threads.c.id, ondelete="CASCADE"),
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
                            [connections.c.id, connections.c.account_id]),
    sa.UniqueConstraint("id", "account_id", name="chat_request_owner"),
    sa.CheckConstraint("credential_generation > 0", name="chat_request_generation"),
    sa.CheckConstraint(
        "state IN ('pending','streaming','completed','interrupted','error','stopped')",
        name="chat_request_state"),
)
sa.Index("ix_chat_requests_owner_time", requests.c.account_id, requests.c.created_at, requests.c.id)
_active = requests.c.state.in_(("pending", "streaming"))
sa.Index("ix_chat_one_active_per_thread", requests.c.thread_id, unique=True,
         postgresql_where=_active, sqlite_where=_active)

messages = sa.Table(
    "chat_messages", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("thread_id", sa.Uuid, sa.ForeignKey(threads.c.id, ondelete="CASCADE"),
              nullable=False),
    sa.Column("request_id", sa.Uuid, sa.ForeignKey(requests.c.id, ondelete="CASCADE"),
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
    sa.CheckConstraint("role IN ('user','assistant') AND sequence > 0 AND part_version = 1",
                       name="chat_message_shape"),
    sa.CheckConstraint("state IN ('complete','partial','interrupted','error','stopped')",
                       name="chat_message_state"),
)

attachments = sa.Table(
    "chat_message_attachments", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("message_id", sa.Uuid, sa.ForeignKey(messages.c.id, ondelete="CASCADE"),
              nullable=False),
    sa.Column("request_id", sa.Uuid, sa.ForeignKey(requests.c.id, ondelete="CASCADE"),
              nullable=False),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("asset_id", sa.Uuid, sa.ForeignKey(media_assets.c.id), nullable=False),
    sa.Column("ordinal", sa.SmallInteger, nullable=False),
    sa.Column("media_type", sa.String(32), nullable=False),
    sa.Column("byte_size", sa.BigInteger, nullable=False),
    sa.Column("width", sa.Integer, nullable=False),
    sa.Column("height", sa.Integer, nullable=False),
    sa.Column("sha256", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("message_id", "ordinal", name="chat_attachment_ordinal"),
    sa.UniqueConstraint("message_id", "asset_id", name="chat_attachment_asset_once"),
    sa.CheckConstraint(
        "ordinal >= 0 AND media_type = 'image/png' AND byte_size > 0 AND width > 0 AND height > 0",
        name="chat_attachment_shape"),
)
sa.Index("ix_chat_attachment_request", attachments.c.request_id, attachments.c.ordinal)

limits = sa.Table(
    "chat_rate_limits", metadata,
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id", ondelete="CASCADE"),
              primary_key=True),
    sa.Column("kind", sa.String(16), primary_key=True),
    sa.Column("window_start", sa.BigInteger, primary_key=True),
    sa.Column("count", sa.Integer, nullable=False),
    sa.CheckConstraint("kind IN ('request','credential') AND count > 0",
                       name="chat_rate_shape"),
)

TABLES = (connections, threads, requests, messages, attachments, limits)
