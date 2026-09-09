"""JOBS-001: durable jobs and explicit upload/generated asset lineage.

Frozen schema snapshot; never import mutable application models here.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_jobs"
down_revision = "0007_media"
branch_labels = depends_on = None

metadata = sa.MetaData()
sa.Table("accounts", metadata, sa.Column("id", sa.Uuid, primary_key=True))
reservations = sa.Table("credit_reservations", metadata, sa.Column("id", sa.Uuid, primary_key=True))
outputs = sa.Table("media_output_allocations", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
    sa.Column("reserved_bytes", sa.BigInteger, nullable=False),
    sa.Column("state", sa.String(16), nullable=False),
    sa.Column("width", sa.Integer, nullable=False),
    sa.Column("height", sa.Integer, nullable=False),
    sa.Column("object_key", sa.String(200)),
    sa.Column("sha256", sa.String(64)),
    sa.Column("byte_size", sa.BigInteger),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("id", "account_id", name="media_output_owner"),
    sa.CheckConstraint("reserved_bytes >= 0 AND width > 0 AND height > 0", name="media_output_bounds"),
    sa.CheckConstraint("state IN ('reserved','storing','ready','released')", name="media_output_state"),
    sa.CheckConstraint("state NOT IN ('storing','ready') OR (object_key IS NOT NULL AND sha256 IS NOT NULL AND byte_size > 0)", name="media_output_sealed"))
sa.Index("ix_media_output_owner", outputs.c.account_id, outputs.c.state)
quotes = sa.Table("job_quotes", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
    sa.Column("request_json", sa.Text, nullable=False),
    sa.Column("catalog_version", sa.String(40), nullable=False),
    sa.Column("credits", sa.Integer, nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("id", "account_id", name="job_quote_owner"),
    sa.CheckConstraint("credits > 0 AND expires_at > created_at", name="job_quote_bounds"))
sa.Index("ix_job_quotes_owner_time", quotes.c.account_id, quotes.c.created_at)
jobs = sa.Table("generation_jobs", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
    sa.Column("operation_id", sa.Uuid, nullable=False),
    sa.Column("quote_id", sa.Uuid, nullable=False, unique=True),
    sa.Column("request_json", sa.Text, nullable=False),
    sa.Column("plan_snapshot", sa.Text, nullable=False),
    sa.Column("pool", sa.String(80), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("reservation_id", sa.Uuid, sa.ForeignKey(reservations.c.id), nullable=False, unique=True),
    sa.Column("output_id", sa.Uuid, nullable=False, unique=True),
    sa.Column("reserve_credits", sa.Integer, nullable=False),
    sa.Column("charged_credits", sa.Integer, nullable=False),
    sa.Column("fence", sa.Integer, nullable=False),
    sa.Column("attempt_id", sa.Uuid),
    sa.Column("lease_until", sa.BigInteger),
    sa.Column("next_poll_at", sa.BigInteger, nullable=False),
    sa.Column("reconcile_count", sa.Integer, nullable=False),
    sa.Column("cancel_requested", sa.Boolean, nullable=False),
    sa.Column("error_code", sa.String(80)),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.Column("deadline_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("account_id", "operation_id", name="job_idempotency"),
    sa.ForeignKeyConstraint(["quote_id", "account_id"], [quotes.c.id, quotes.c.account_id]),
    sa.ForeignKeyConstraint(["output_id", "account_id"], [outputs.c.id, outputs.c.account_id]),
    sa.CheckConstraint("status IN ('queued','claimed','running','uploading','reconciling','succeeded','failed','cancelled')", name="job_state"),
    sa.CheckConstraint("reserve_credits > 0 AND charged_credits >= 0 AND charged_credits <= reserve_credits AND fence >= 0 AND reconcile_count >= 0", name="job_bounds"))
sa.Index("ix_jobs_owner_time", jobs.c.account_id, jobs.c.created_at, jobs.c.id)
sa.Index("ix_jobs_pool_state", jobs.c.pool, jobs.c.status, jobs.c.next_poll_at)
attempts = sa.Table("generation_attempts", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("job_id", sa.Uuid, sa.ForeignKey(jobs.c.id), nullable=False),
    sa.Column("fence", sa.Integer, nullable=False),
    sa.Column("worker_id", sa.String(80), nullable=False),
    sa.Column("state", sa.String(16), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("closed_at", sa.BigInteger),
    sa.UniqueConstraint("job_id", "fence", name="attempt_fence"),
    sa.CheckConstraint("fence > 0 AND state IN ('claimed','running','succeeded','failed','cancelled','expired')", name="attempt_state"))
outbox = sa.Table("job_outbox", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("job_id", sa.Uuid, sa.ForeignKey(jobs.c.id), nullable=False),
    sa.Column("event_type", sa.String(40), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.UniqueConstraint("job_id", "event_type", name="job_event_once"))
TABLES = (quotes, jobs, attempts, outbox)


def upgrade():
    conn = op.get_bind()
    outputs.create(conn)
    op.add_column("media_assets", sa.Column("upload_id", sa.Uuid, nullable=True))
    op.add_column("media_assets", sa.Column("output_id", sa.Uuid, nullable=True))
    conn.execute(sa.text("UPDATE media_assets SET upload_id = id"))
    # Locate the old unnamed composite FK, named by PostgreSQL automatically.
    old = [fk for fk in sa.inspect(conn).get_foreign_keys("media_assets")
           if fk["referred_table"] == "media_uploads" and fk["constrained_columns"] == ["id", "account_id"]]
    if len(old) != 1:
        raise RuntimeError("Expected the original media upload ownership constraint")
    convention = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("media_assets", naming_convention=convention) as batch:
        batch.drop_constraint(old[0]["name"] or "fk_media_assets_id_media_uploads", type_="foreignkey")
        batch.create_foreign_key("media_asset_upload_owner", "media_uploads",
                                 ["upload_id", "account_id"], ["id", "account_id"])
        batch.create_foreign_key("media_asset_output_owner", "media_output_allocations",
                                 ["output_id", "account_id"], ["id", "account_id"])
        batch.create_check_constraint("media_asset_source",
            "(upload_id IS NOT NULL AND output_id IS NULL AND id = upload_id) OR "
            "(output_id IS NOT NULL AND upload_id IS NULL AND id = output_id)")
    for table in TABLES:
        table.create(conn)


def downgrade():
    raise RuntimeError("Jobs own financial obligations and media; use a reviewed forward migration")
