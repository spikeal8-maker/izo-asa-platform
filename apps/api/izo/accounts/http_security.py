"""Shared same-origin and bounded-body guards for Accounts and staff commands."""
from fastapi.responses import JSONResponse
from .security import AuthError


class AuthBodyLimit:
    """Bound auth/admin request bodies before JSON parsing, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or not scope["path"].startswith(("/api/v1/auth/", "/api/v1/admin/"))
                or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > 8192:
                response = JSONResponse({"error": {"code": "request_too_large"}}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


def same_origin(request, instance):
    origins = request.headers.getlist("origin")
    if (len(origins) != 1 or origins[0] not in instance.policy.origins
            or request.headers.get("x-izo-request") != "web"
            or request.headers.get("sec-fetch-site") == "cross-site"):
        raise AuthError(403, "origin_rejected")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise AuthError(415, "json_required")

