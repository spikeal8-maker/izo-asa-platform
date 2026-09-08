"""Composition root: no migrations, generation loops or external calls on import."""
import json
import logging
import time
import uuid
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import Settings, settings
from .contracts import Modality
from .health import dependencies_ready
from .accounts.routes import attach_accounts

logger = logging.getLogger("izo.http")


class CapabilityStatus(BaseModel):
    modality: Modality
    available: bool
    reason: str


class FoundationStatus(BaseModel):
    stage: str
    build_sha: str
    capabilities: list[CapabilityStatus]


def create_app(config: Settings | None = None,
               readiness: Callable[[], bool] | None = None) -> FastAPI:
    config = config or settings()
    probe = readiness or (lambda: dependencies_ready(config))
    app = FastAPI(title="IZO ASA Platform", version="0.1.0", docs_url=None, redoc_url=None)
    attach_accounts(app, config)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # Never log raw exceptions: provider/config errors can contain secrets.
            # This handles errors before a response starts; streaming needs its
            # own lifecycle/error handling when that feature is implemented.
            response = JSONResponse(
                {"error": {"code": "internal_error", "request_id": request_id}},
                status_code=500,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        level = logging.ERROR if response.status_code >= 500 else logging.INFO
        logger.log(level, json.dumps({"event": "http_request", "request_id": request_id,
                                "method": request.method, "status": response.status_code,
                                "duration_ms": round((time.monotonic() - started) * 1000)}))
        return response

    @app.get("/api/health/live")
    def live() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/health/ready", include_in_schema=False)
    def ready():
        try:
            ok = bool(probe())
        except Exception:
            ok = False
        return JSONResponse({"ready": ok}, status_code=200 if ok else 503)

    @app.get("/api/v1/foundation", response_model=FoundationStatus)
    def foundation() -> FoundationStatus:
        return FoundationStatus(stage="foundation", build_sha=config.build_sha,
            capabilities=[CapabilityStatus(modality=m, available=False,
                          reason="not_implemented") for m in Modality])

    return app
