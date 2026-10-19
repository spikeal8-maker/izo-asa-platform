"""Persist conversation variants without rewriting existing messages or requests."""
from alembic import op
import sqlalchemy as sa

revision = "0018_chat_conversation_graph"
down_revision = "0017_chat_manual_title"
branch_labels = depends_on = None


def _frozen_tables(metadata):
    branches = sa.Table("chat_branches", metadata,
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("thread_id", sa.Uuid, sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("id", "thread_id", name="chat_branch_thread"))
    graphs = sa.Table("chat_thread_graphs", metadata,
        sa.Column("thread_id", sa.Uuid, sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("active_branch_id", sa.Uuid, nullable=False),
        sa.Column("revision", sa.BigInteger, nullable=False),
        sa.ForeignKeyConstraint(["active_branch_id", "thread_id"],
            ["chat_branches.id", "chat_branches.thread_id"], ondelete="CASCADE"),
        sa.CheckConstraint("revision >= 0", name="chat_graph_revision"))
    turns = sa.Table("chat_turns", metadata,
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("thread_id", sa.Uuid, nullable=False),
        sa.Column("branch_id", sa.Uuid, nullable=False),
        sa.Column("user_message_id", sa.Uuid, nullable=False),
        sa.Column("user_role", sa.String(12), nullable=False, server_default="user"),
        sa.Column("turn_sequence", sa.BigInteger, nullable=False),
        sa.Column("assistant_display_sequence", sa.BigInteger, nullable=False),
        sa.ForeignKeyConstraint(["branch_id", "thread_id"],
            ["chat_branches.id", "chat_branches.thread_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_message_id", "thread_id", "user_role"],
            ["chat_messages.id", "chat_messages.thread_id", "chat_messages.role"]),
        sa.UniqueConstraint("id", "branch_id", "thread_id", name="chat_turn_branch_thread"),
        sa.UniqueConstraint("branch_id", "user_message_id", name="chat_turn_user_once"),
        sa.UniqueConstraint("branch_id", "turn_sequence", name="chat_turn_order"),
        sa.CheckConstraint("user_role = 'user' AND turn_sequence > 0 AND assistant_display_sequence > turn_sequence",
            name="chat_turn_shape"))
    attempts = sa.Table("chat_assistant_attempts", metadata,
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("turn_id", sa.Uuid, nullable=False),
        sa.Column("branch_id", sa.Uuid, nullable=False),
        sa.Column("thread_id", sa.Uuid, nullable=False),
        sa.Column("assistant_message_id", sa.Uuid, nullable=False, unique=True),
        sa.Column("assistant_role", sa.String(12), nullable=False, server_default="assistant"),
        sa.Column("ordinal", sa.BigInteger, nullable=False),
        sa.Column("source_attempt_id", sa.Uuid),
        sa.ForeignKeyConstraint(["id", "thread_id"],
            ["chat_requests.id", "chat_requests.thread_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id", "branch_id", "thread_id"],
            ["chat_turns.id", "chat_turns.branch_id", "chat_turns.thread_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assistant_message_id", "thread_id", "id", "assistant_role"],
            ["chat_messages.id", "chat_messages.thread_id", "chat_messages.request_id", "chat_messages.role"]),
        sa.ForeignKeyConstraint(["source_attempt_id", "turn_id", "branch_id", "thread_id"],
            ["chat_assistant_attempts.id", "chat_assistant_attempts.turn_id",
             "chat_assistant_attempts.branch_id", "chat_assistant_attempts.thread_id"]),
        sa.UniqueConstraint("id", "turn_id", "branch_id", "thread_id", name="chat_attempt_turn"),
        sa.UniqueConstraint("turn_id", "ordinal", name="chat_attempt_order"),
        sa.CheckConstraint("assistant_role = 'assistant' AND ordinal > 0", name="chat_attempt_shape"))
    selections = sa.Table("chat_turn_selections", metadata,
        sa.Column("turn_id", sa.Uuid, primary_key=True),
        sa.Column("branch_id", sa.Uuid, nullable=False),
        sa.Column("thread_id", sa.Uuid, nullable=False),
        sa.Column("attempt_id", sa.Uuid, nullable=False),
        sa.ForeignKeyConstraint(["attempt_id", "turn_id", "branch_id", "thread_id"],
            ["chat_assistant_attempts.id", "chat_assistant_attempts.turn_id",
             "chat_assistant_attempts.branch_id", "chat_assistant_attempts.thread_id"], ondelete="CASCADE"))
    contexts = sa.Table("chat_request_contexts", metadata,
        sa.Column("request_id", sa.Uuid, primary_key=True),
        sa.Column("thread_id", sa.Uuid, nullable=False),
        sa.Column("turn_id", sa.Uuid, nullable=False),
        sa.Column("branch_id", sa.Uuid, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("provenance", sa.String(24), nullable=False),
        sa.Column("revision", sa.BigInteger),
        sa.Column("snapshot", sa.JSON(none_as_null=True)),
        sa.Column("digest", sa.String(64)),
        sa.ForeignKeyConstraint(["request_id", "thread_id"],
            ["chat_requests.id", "chat_requests.thread_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id", "branch_id", "thread_id"],
            ["chat_turns.id", "chat_turns.branch_id", "chat_turns.thread_id"]),
        sa.CheckConstraint("kind IN ('send','regenerate') AND provenance IN ('admission','legacy_claim','legacy_unrecorded')",
            name="chat_context_provenance"),
        sa.CheckConstraint("(provenance = 'legacy_unrecorded' AND snapshot IS NULL AND digest IS NULL AND revision IS NULL) OR "
            "(provenance != 'legacy_unrecorded' AND snapshot IS NOT NULL AND digest IS NOT NULL AND revision >= 0)",
            name="chat_context_snapshot"))
    return graphs, branches, turns, attempts, selections, contexts


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    threads = sa.Table("chat_threads", metadata,
        sa.Column("id", sa.Uuid), sa.Column("created_at", sa.BigInteger))
    requests = sa.Table("chat_requests", metadata,
        sa.Column("id", sa.Uuid), sa.Column("thread_id", sa.Uuid), sa.Column("state", sa.String(20)))
    messages = sa.Table("chat_messages", metadata,
        sa.Column("id", sa.Uuid), sa.Column("thread_id", sa.Uuid),
        sa.Column("request_id", sa.Uuid), sa.Column("role", sa.String(12)),
        sa.Column("state", sa.String(16)), sa.Column("sequence", sa.BigInteger))
    for name, table, columns in (
        ("ux_chat_request_graph_identity", "chat_requests", ["id", "thread_id"]),
        ("ux_chat_message_graph_role", "chat_messages", ["id", "thread_id", "role"]),
        ("ux_chat_message_graph_request", "chat_messages", ["id", "thread_id", "request_id", "role"]),
    ):
        op.create_index(name, table, columns, unique=True)
    graphs, branches, turns, attempts, selections, contexts = _frozen_tables(metadata)
    for table in (branches, graphs, turns, attempts, selections, contexts):
        table.create(bind)
    bind.execute(sa.insert(branches).from_select(["id", "thread_id", "created_at"],
        sa.select(threads.c.id, threads.c.id, threads.c.created_at)))
    bind.execute(sa.insert(graphs).from_select(["thread_id", "active_branch_id", "revision"],
        sa.select(threads.c.id, threads.c.id, sa.literal(0))))
    user, assistant = messages.alias("graph_user"), messages.alias("graph_assistant")
    pairs = user.join(assistant, sa.and_(assistant.c.request_id == user.c.request_id,
        assistant.c.thread_id == user.c.thread_id, assistant.c.role == "assistant"))
    bind.execute(sa.insert(turns).from_select(
        ["id", "thread_id", "branch_id", "user_message_id", "turn_sequence", "assistant_display_sequence"],
        sa.select(user.c.id, user.c.thread_id, user.c.thread_id, user.c.id,
                  user.c.sequence, assistant.c.sequence).select_from(pairs).where(user.c.role == "user")))
    bind.execute(sa.insert(attempts).from_select(
        ["id", "turn_id", "thread_id", "branch_id", "assistant_message_id", "ordinal"],
        sa.select(assistant.c.request_id, user.c.id, user.c.thread_id, user.c.thread_id,
                  assistant.c.id, sa.literal(1)).select_from(pairs).where(user.c.role == "user")))
    total = bind.execute(sa.select(sa.func.count()).select_from(requests)).scalar_one()
    mapped = bind.execute(sa.select(sa.func.count()).select_from(attempts)).scalar_one()
    if total != mapped:
        raise RuntimeError("Graph migration requires every legacy request's original user/assistant pair")
    inconsistent = bind.execute(sa.select(requests.c.id).join(messages,
        sa.and_(messages.c.request_id == requests.c.id, messages.c.role == "assistant")).where(
        requests.c.state == "completed", messages.c.state != "complete").limit(1)).first()
    if inconsistent:
        raise RuntimeError("Graph migration found inconsistent completed request evidence")
    bind.execute(sa.insert(selections).from_select(
        ["turn_id", "thread_id", "branch_id", "attempt_id"],
        sa.select(attempts.c.turn_id, attempts.c.thread_id, attempts.c.branch_id,
            attempts.c.id).join(requests, requests.c.id == attempts.c.id)
            .where(requests.c.state == "completed")))
    # No historical execution context is invented. Only an actual later pending
    # claim may replace this explicit absence with legacy_claim provenance.
    bind.execute(sa.insert(contexts).from_select(
        ["request_id", "thread_id", "turn_id", "branch_id", "kind", "provenance"],
        sa.select(attempts.c.id, attempts.c.thread_id, attempts.c.turn_id,
                  attempts.c.branch_id, sa.literal("send"), sa.literal("legacy_unrecorded"))))


def downgrade():
    raise RuntimeError("Conversation variants and context evidence are retained; use a reviewed forward migration")
