"""Bounded media transport and redacted validation; no changed auth defaults."""
import asyncio
from threading import BoundedSemaphore
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from ..accounts.security import AuthError
from ..accounts.http_security import same_origin
from ..entitlements.schemas import EntitlementError
from .schemas import MAX_INPUT, MediaError


class MediaRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError:
                return JSONResponse({"error": {"code": "invalid_input"}}, status_code=422)
            except (MediaError, AuthError, EntitlementError) as exc:
                return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)
        return handler


def origin(request, auth, *, binary=False):
    required = "application/octet-stream" if binary else "application/json"
    same_origin(request, auth, content_type=required)
    if len(request.headers.getlist("content-type")) != 1:
        raise MediaError(415, "content_type_rejected")


def query(request, allowed=()):
    keys = [key for key, _ in request.query_params.multi_items()]
    if set(keys) - set(allowed) or len(keys) != len(set(keys)):
        raise MediaError(422, "invalid_input")


class MediaTransportGuard:
    """At most two media HTTP requests per process; bounded body/time incl. chunks.

    This is a conservative dev/test cap, not distributed production rate limiting.
    Holding a slot through send also bounds simultaneous buffered downloads.
    """
    def __init__(self, app):
        self.app, self.slots = app, BoundedSemaphore(2)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/media/"):
            return await self.app(scope, receive, send)
        if not self.slots.acquire(blocking=False):
            return await JSONResponse({"error": {"code": "media_busy"}}, 429,
                                      headers={"Retry-After": "1"})(scope, receive, send)
        try:
            if scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
                return await self.app(scope, receive, send)
            if any(k.lower() == b"content-encoding" for k, _ in scope.get("headers", [])):
                return await JSONResponse({"error": {"code": "encoding_rejected"}}, 415)(scope, receive, send)
            maximum = MAX_INPUT if scope["path"].endswith("/content") else 8192

            async def read():
                chunks, count = [], 0
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return None
                    chunk = message.get("body", b"")
                    count += len(chunk)
                    if count > maximum:
                        raise MediaError(413, "request_too_large")
                    chunks.append(chunk)
                    if not message.get("more_body", False):
                        return b"".join(chunks)
            try:
                body = await asyncio.wait_for(read(), timeout=30)
            except asyncio.TimeoutError:
                return await JSONResponse({"error": {"code": "request_timeout"}}, 408)(scope, receive, send)
            except MediaError as exc:
                return await JSONResponse({"error": {"code": exc.code}}, exc.status)(scope, receive, send)
            if body is None:
                return
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()
            await self.app(scope, replay, send)
        finally:
            self.slots.release()
