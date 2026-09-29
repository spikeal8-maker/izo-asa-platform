"""Explicit foreground test worker. No thread, DB connection or loop on API import."""
import argparse
import hashlib
import io
import logging
import os
import signal
from threading import Event

from .catalog import JobSettings
from .execution import JobRunner
from .recovery import recover, reconcile_one

logger = logging.getLogger("izo.jobs")


def render_test_image(draft):
    """Diagnostic image, NOT inference. Prompt is data, never a shell/workflow."""
    from PIL import Image, ImageDraw
    tint = tuple(hashlib.sha256(draft.prompt.encode("utf-8")).digest()[:3])
    with Image.new("RGB", (draft.width, draft.height), tint) as image:
        ImageDraw.Draw(image).text((4, 4), "TEST ONLY", fill="white")
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue()


def step(runner):
    recover(runner)
    recovered = reconcile_one(runner)
    claim = runner.claim()
    if claim is not None:
        runner.execute(claim, render_test_image)
    return recovered or claim is not None


def main():
    parser = argparse.ArgumentParser(description="IZO ASA isolated test-image executor")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--worker-id", default="test-worker")
    args = parser.parse_args()
    if os.environ.get("IZO_ENVIRONMENT") not in {"development", "test"}:
        raise SystemExit("Explicit development/test environment required")
    policy = JobSettings()
    if not policy.enabled:
        raise SystemExit("IZO_JOBS_ENABLED must explicitly enable the test executor")
    from ..config import Settings
    from ..accounts.repository import create_auth_engine
    from ..accounts.service import AuthService
    from ..accounts.settings import AuthSettings
    from ..media.objects import MediaStore
    from .service import JobService
    config = Settings()
    engine = create_auth_engine(config)
    runner = JobRunner(JobService(AuthService(engine, AuthSettings()), policy), MediaStore(config), args.worker_id)
    stopping = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.set())
    try:
        while not stopping.is_set():
            try:
                step(runner)
            except Exception:
                logger.error("worker_iteration_failed")  # No raw prompt/secret-bearing exceptions.
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
