"""Opt-in fal.ai worker. Provider credentials exist only in this process environment."""
import argparse
import logging
import os
import signal
from threading import Event

from ..providers.fal import FalAdapter, FalSettings
from .catalog import FAL_POOL, JobSettings
from .execution import JobRunner
from .provider_execution import FalJobExecutor, recover_fal
from .recovery import reconcile_one

logger = logging.getLogger("izo.jobs.fal")


def step(executor):
    changed = recover_fal(executor.runner)
    if reconcile_one(executor.runner):
        return True
    claim = executor.runner.claim(resume_external=True)
    if claim is not None:
        executor.execute(claim)
    return bool(changed or claim is not None)


def main():
    parser = argparse.ArgumentParser(description="IZO ASA fal.ai FLUX.2 [klein] worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--worker-id", default="fal-worker")
    args = parser.parse_args()
    if os.environ.get("IZO_ENVIRONMENT") not in {"development", "test"}:
        raise SystemExit("Explicit development/test environment required")
    jobs = JobSettings()
    if not jobs.enabled:
        raise SystemExit("IZO_JOBS_ENABLED must explicitly enable jobs")
    fal = FalSettings()
    try:
        fal.require_worker_ready()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
    minimum_lease = max(fal.request_timeout_seconds, fal.media_timeout_seconds) + 20
    if jobs.lease_seconds < minimum_lease:
        raise SystemExit("fal worker lease must exceed its longest bounded network operation")

    from ..config import Settings
    from ..accounts.repository import create_auth_engine
    from ..accounts.service import AuthService
    from ..accounts.settings import AuthSettings
    from ..media.objects import MediaStore
    from .service import JobService
    config = Settings()
    engine = create_auth_engine(config)
    service = JobService(AuthService(engine, AuthSettings()), jobs, fal)
    runner = JobRunner(service, MediaStore(config), args.worker_id, pool=FAL_POOL)
    executor = FalJobExecutor(runner, FalAdapter(fal))
    stopping = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.set())
    try:
        while not stopping.is_set():
            try:
                recover_fal(runner)
                if reconcile_one(runner):
                    continue
                claim = runner.claim(resume_external=True)
                if claim is not None:
                    executor.execute(claim, stopping=stopping)
            except Exception:
                logger.error("fal_worker_iteration_failed")
                if args.once:
                    raise SystemExit(1) from None
                stopping.wait(2)
            if args.once:
                break
            stopping.wait(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
