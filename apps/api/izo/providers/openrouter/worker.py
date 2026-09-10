"""Explicit OpenRouter worker. The public API container never receives its credential."""
import argparse
import json
import logging
import os
import signal
from threading import Event

import sqlalchemy as sa

from ...accounts.jobs_access import lock_worker_owner
from ...accounts.repository import create_auth_engine
from ...accounts.service import AuthService
from ...accounts.settings import AuthSettings
from ...config import Settings
from ...jobs import catalog, repository as repo, tables as jobs
from ...jobs.execution import JobRunner
from ...jobs.recovery import reconcile_one
from ...jobs.schemas import JobError, QuoteInput
from ...jobs.service import JobService
from ...media import codec
from ...media.objects import MediaStore
from .client import ProviderError, generate
from .config import OpenRouterSecret, OpenRouterSettings, parse_execution

logger = logging.getLogger("izo.providers.openrouter")


def recover_without_redispatch(runner, limit=32):
    """Only claimed-before-start may be requeued; expired running is ambiguous."""
    now = runner.auth.now()
    with runner.auth.engine.connect() as conn:
        rows = conn.execute(sa.select(jobs.jobs.c.id, jobs.jobs.c.account_id).where(
            jobs.jobs.c.pool == catalog.OPENROUTER_POOL,
            sa.or_(sa.and_(jobs.jobs.c.status == "queued", jobs.jobs.c.deadline_at <= now),
                   sa.and_(jobs.jobs.c.status.in_(("claimed", "running")), jobs.jobs.c.lease_until <= now)))
            .order_by(jobs.jobs.c.updated_at, jobs.jobs.c.id).limit(limit)).all()
    for job_id, owner in rows:
        with runner.auth.engine.begin() as conn:
            state = lock_worker_owner(conn, owner, skip_locked=True)
            if state is None:
                continue
            row = repo.load(conn, owner, job_id)
            if row["status"] == "queued" and row["deadline_at"] <= now:
                runner.service.release_terminal(conn, row, "failed", "executor_deadline")
            elif row["status"] == "claimed" and row["lease_until"] <= now:
                repo.close_attempt(conn, row, "expired", now)
                repo.change(conn, job_id, now, status="queued", attempt_id=None, lease_until=None)
            elif row["status"] == "running" and row["lease_until"] <= now:
                repo.close_attempt(conn, row, "failed", now)
                repo.change(conn, job_id, now, status="reconciling", lease_until=0,
                            next_poll_at=now, error_code="provider_outcome_unknown")
                repo.event(conn, job_id, "provider_reconciliation_required", now)


def execute_one(runner, settings, secret):
    claim = runner.claim()
    if claim is None:
        return False
    try:
        draft = runner.start(claim)
        if draft is None:
            return True
        snapshot = parse_execution(runner.execution_snapshot(claim))
        api_key = secret.require()
    except Exception:
        try:
            runner.fail_before_output(claim)
        except Exception:
            pass
        return True
    try:
        result = generate(snapshot, draft.prompt, api_key, timeout=settings.timeout_seconds)
    except ProviderError as exc:
        try:
            runner.provider_uncertain(claim, exc.code)
        except JobError:
            pass
        return True
    try:
        runner.record_provider_result(claim, provider_ref=result.provider_ref,
                                      provider_cost_usd=result.cost_usd)
        image = codec.decode(result.data, result.media_type, draft.width, draft.height,
                             catalog.output_bound(draft.width, draft.height))
        key = runner.seal(claim, image)
        if key is None:
            return True
        runner.store.put(key, image.data, "image/png")
        runner.finish(claim, image.data, provider_ref=result.provider_ref,
                      provider_cost_usd=result.cost_usd)
    except Exception:
        try:
            runner.provider_uncertain(claim, "provider_result_storage_uncertain")
        except JobError:
            try:
                runner.uncertain(claim)
            except JobError:
                pass
    return True


def main():
    parser = argparse.ArgumentParser(description="IZO ASA OpenRouter image worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--worker-id", default="openrouter-worker")
    args = parser.parse_args()
    if os.environ.get("IZO_ENVIRONMENT") not in {"development", "test"}:
        raise SystemExit("Current release only permits explicit development/test provider worker")
    settings = OpenRouterSettings()
    if not settings.enabled:
        raise SystemExit("IZO_OPENROUTER_ENABLED must explicitly enable this provider")
    secret = OpenRouterSecret(); secret.require()
    config = Settings(); engine = create_auth_engine(config)
    service = JobService(AuthService(engine, AuthSettings()), openrouter=settings)
    runner = JobRunner(service, MediaStore(config), args.worker_id, catalog.OPENROUTER_POOL)
    stopping = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.set())
    try:
        while not stopping.is_set():
            try:
                recover_without_redispatch(runner)
                worked = reconcile_one(runner) or execute_one(runner, settings, secret)
            except Exception:
                logger.error("openrouter_worker_iteration_failed")
                worked = False
                if args.once:
                    raise SystemExit(1) from None
            if args.once:
                break
            stopping.wait(1 if worked else 2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
