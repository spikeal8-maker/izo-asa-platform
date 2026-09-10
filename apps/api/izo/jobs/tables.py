"""Jobs owns queue/attempt/outbox metadata, not Account, wallet or media rows."""
import sqlalchemy as sa
from ..media.tables import outputs
from ..credits.tables import reservations

metadata = sa.MetaData()
sa.Table("accounts", metadata, sa.Column("id", sa.Uuid, primary_key=True))
quotes = sa.Table("job_quotes", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
    sa.Column("request_json", sa.Text, nullable=False),
    sa.Column("catalog_version", sa.String(40), nullable=False),
    sa.Column("credits", sa.Integer, nullable=False),
    sa.Column("execution_json", sa.Text),
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
    sa.Column("execution_json", sa.Text),
    sa.Column("provider_ref", sa.String(200)),
    sa.Column("provider_cost_usd", sa.Numeric(14, 6)),
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
