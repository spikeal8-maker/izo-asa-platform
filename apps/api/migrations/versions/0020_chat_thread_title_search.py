"""Backfill the private, versioned literal title key without changing history."""
from alembic import op
import sqlalchemy as sa

from izo.chat.thread_title_search_v1 import check_runtime, title_key

revision = "0020_chat_thread_title_search"
down_revision = "0019_chat_message_branches"
branch_labels = depends_on = None


def upgrade():
    check_runtime()
    bind = op.get_bind()
    if bind.dialect.name == "sqlite" and bind.exec_driver_sql("PRAGMA foreign_keys").scalar():
        raise RuntimeError("SQLite batch migration requires foreign_keys OFF before the transaction")
    op.add_column("chat_threads", sa.Column("title_search_key", sa.String(240), nullable=True))
    threads = sa.table("chat_threads", sa.column("id", sa.Uuid),
        sa.column("title", sa.String(120)), sa.column("title_search_key", sa.String(240)))
    boundary = None
    while True:
        query = sa.select(threads.c.id, threads.c.title).order_by(threads.c.id).limit(500)
        if boundary is not None:
            query = query.where(threads.c.id > boundary)
        rows = bind.execute(query).mappings().all()
        if not rows:
            break
        bind.execute(sa.update(threads).where(threads.c.id == sa.bindparam("thread_id"))
            .values(title_search_key=sa.bindparam("search_key")),
            [{"thread_id": row["id"], "search_key": title_key(row["title"])} for row in rows])
        boundary = rows[-1]["id"]
    with op.batch_alter_table("chat_threads") as batch:
        batch.alter_column("title_search_key", existing_type=sa.String(240), nullable=False)


def downgrade():
    raise RuntimeError("Title search keys are retained; use a reviewed forward migration")
