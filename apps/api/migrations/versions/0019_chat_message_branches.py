"""Retain Graph evidence while adding immutable branch membership and selection."""
from alembic import op
import sqlalchemy as sa

revision = "0019_chat_message_branches"
down_revision = "0018_chat_conversation_graph"
branch_labels = depends_on = None
NAMES = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
         "pk": "pk_%(table_name)s"}


def _fk_name(bind, table, columns):
    match = next(item for item in sa.inspect(bind).get_foreign_keys(table)
                 if item["constrained_columns"] == columns)
    return match["name"] or f"fk_{table}_{columns[0]}_{match['referred_table']}"


def _membership_tables():
    # Frozen migration definitions, independent of future runtime registrations.
    metadata = sa.MetaData()
    for name, columns in (
        ("chat_branches", ("id", "thread_id")),
        ("chat_turns", ("id", "thread_id", "branch_id")),
        ("chat_assistant_attempts", ("id", "turn_id", "thread_id", "branch_id")),
    ):
        sa.Table(name, metadata, *(sa.Column(column, sa.Uuid) for column in columns))
    turns = sa.Table("chat_branch_turns", metadata,
        sa.Column("branch_id", sa.Uuid, primary_key=True),
        sa.Column("turn_id", sa.Uuid, primary_key=True),
        sa.Column("thread_id", sa.Uuid, nullable=False),
        sa.ForeignKeyConstraint(["branch_id", "thread_id"],
            ["chat_branches.id", "chat_branches.thread_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id", "thread_id"],
            ["chat_turns.id", "chat_turns.thread_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("turn_id", "branch_id", "thread_id", name="chat_branch_turn_identity"))
    attempts = sa.Table("chat_branch_attempts", metadata,
        sa.Column("branch_id", sa.Uuid, primary_key=True),
        sa.Column("attempt_id", sa.Uuid, primary_key=True),
        sa.Column("turn_id", sa.Uuid, nullable=False),
        sa.Column("thread_id", sa.Uuid, nullable=False),
        sa.ForeignKeyConstraint(["turn_id", "branch_id", "thread_id"],
            ["chat_branch_turns.turn_id", "chat_branch_turns.branch_id", "chat_branch_turns.thread_id"],
            ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id", "turn_id", "thread_id"],
            ["chat_assistant_attempts.id", "chat_assistant_attempts.turn_id", "chat_assistant_attempts.thread_id"],
            ondelete="CASCADE"),
        sa.UniqueConstraint("attempt_id", "turn_id", "branch_id", "thread_id", name="chat_branch_attempt_identity"))
    return metadata, turns, attempts


def upgrade():
    bind = op.get_bind()
    # PostgreSQL performs transactional ALTERs. SQLite's test-only batch table
    # replacement needs FK disabling before its transaction, then a full check.
    if bind.dialect.name == "sqlite" and bind.exec_driver_sql("PRAGMA foreign_keys").scalar():
        raise RuntimeError("SQLite batch migration requires foreign_keys OFF before the transaction")
    for name in ("parent_branch_id", "fork_from_turn_id", "fork_source_attempt_id"):
        op.add_column("chat_branches", sa.Column(name, sa.Uuid))
    op.add_column("chat_branches", sa.Column("branch_ordinal", sa.BigInteger,
        nullable=False, server_default="1"))
    with op.batch_alter_table("chat_turns", naming_convention=NAMES) as batch:
        batch.create_unique_constraint("chat_turn_thread", ["id", "thread_id"])
    with op.batch_alter_table("chat_assistant_attempts", naming_convention=NAMES) as batch:
        batch.create_unique_constraint("chat_attempt_thread_turn", ["id", "turn_id", "thread_id"])
    metadata, members, variants = _membership_tables()
    members.create(bind)
    variants.create(bind)
    turns, attempts = metadata.tables["chat_turns"], metadata.tables["chat_assistant_attempts"]
    bind.execute(sa.insert(members).from_select(["branch_id", "turn_id", "thread_id"],
        sa.select(turns.c.branch_id, turns.c.id, turns.c.thread_id)))
    bind.execute(sa.insert(variants).from_select(["branch_id", "attempt_id", "turn_id", "thread_id"],
        sa.select(attempts.c.branch_id, attempts.c.id, attempts.c.turn_id, attempts.c.thread_id)))
    table = "chat_assistant_attempts"
    turn_fk = _fk_name(bind, table, ["turn_id", "branch_id", "thread_id"])
    source_fk = _fk_name(bind, table, ["source_attempt_id", "turn_id", "branch_id", "thread_id"])
    with op.batch_alter_table(table, naming_convention=NAMES) as batch:
        batch.drop_constraint(turn_fk, type_="foreignkey")
        batch.drop_constraint(source_fk, type_="foreignkey")
        batch.create_foreign_key("chat_attempt_membership", "chat_branch_turns",
            ["turn_id", "branch_id", "thread_id"], ["turn_id", "branch_id", "thread_id"], ondelete="CASCADE")
        batch.create_foreign_key("chat_attempt_source_membership", "chat_branch_attempts",
            ["source_attempt_id", "turn_id", "branch_id", "thread_id"],
            ["attempt_id", "turn_id", "branch_id", "thread_id"])
    table = "chat_turn_selections"
    old_fk = _fk_name(bind, table, ["attempt_id", "turn_id", "branch_id", "thread_id"])
    old_pk = sa.inspect(bind).get_pk_constraint(table)["name"] or "pk_chat_turn_selections"
    with op.batch_alter_table(table, naming_convention=NAMES) as batch:
        batch.drop_constraint(old_fk, type_="foreignkey")
        batch.drop_constraint(old_pk, type_="primary")
        batch.create_primary_key("chat_branch_selection_pk", ["turn_id", "branch_id"])
        batch.create_foreign_key("chat_selection_membership", "chat_branch_attempts",
            ["attempt_id", "turn_id", "branch_id", "thread_id"],
            ["attempt_id", "turn_id", "branch_id", "thread_id"], ondelete="CASCADE")
    with op.batch_alter_table("chat_branches", naming_convention=NAMES) as batch:
        batch.create_unique_constraint("chat_branch_order", ["thread_id", "branch_ordinal"])
        batch.create_foreign_key("chat_branch_parent", "chat_branches",
            ["parent_branch_id", "thread_id"], ["id", "thread_id"])
        batch.create_foreign_key("chat_branch_fork_turn", "chat_branch_turns",
            ["fork_from_turn_id", "parent_branch_id", "thread_id"], ["turn_id", "branch_id", "thread_id"])
        batch.create_foreign_key("chat_branch_fork_attempt", "chat_branch_attempts",
            ["fork_source_attempt_id", "fork_from_turn_id", "parent_branch_id", "thread_id"],
            ["attempt_id", "turn_id", "branch_id", "thread_id"])
        batch.create_check_constraint("chat_branch_shape",
            "(parent_branch_id IS NULL AND fork_from_turn_id IS NULL AND "
            "fork_source_attempt_id IS NULL AND branch_ordinal = 1 AND id = thread_id) OR "
            "(parent_branch_id IS NOT NULL AND fork_from_turn_id IS NOT NULL AND "
            "fork_source_attempt_id IS NOT NULL AND parent_branch_id != id AND branch_ordinal > 1)")
    with op.batch_alter_table("chat_request_contexts", naming_convention=NAMES) as batch:
        batch.drop_constraint("chat_context_provenance", type_="check")
        batch.create_check_constraint("chat_context_provenance",
            "kind IN ('send','regenerate','edit') AND provenance IN ('admission','legacy_claim','legacy_unrecorded')")
    if bind.dialect.name == "sqlite" and bind.exec_driver_sql("PRAGMA foreign_key_check").all():
        raise RuntimeError("Branch migration produced invalid retained relationships")


def downgrade():
    raise RuntimeError("Conversation branches and original evidence are retained; use a reviewed forward migration")
