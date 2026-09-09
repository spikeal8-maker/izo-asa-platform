"""Private image endpoints. All commands use the existing server session."""
from functools import lru_cache
from uuid import UUID
from fastapi import APIRouter, Body, Query, Request, Response
from ..accounts.schemas import AuthErrorView
from .http import MediaRoute, MediaTransportGuard, origin, query
from .schemas import AssetList, AssetView, DownloadView, EmptyCommand, UploadIntent, UploadView
from .service import MediaService


def attach_media(app, accounts, config):
    @lru_cache(maxsize=1)
    def store():
        from .objects import MediaStore
        return MediaStore(config)

    def instance(request, *, mutation=False, binary=False):
        auth = accounts(request)
        if mutation:
            origin(request, auth, binary=binary)
        objects = getattr(request.app.state, "media_store", None)
        return MediaService(auth, objects if objects is not None else store()), request.cookies.get(auth.policy.cookie_name)

    router = APIRouter(prefix="/api/v1/media", tags=["media"], route_class=MediaRoute,
        responses={code: {"model": AuthErrorView} for code in ("4XX", 422, 503)})

    @router.post("/uploads", response_model=UploadView, status_code=201)
    def begin(data: UploadIntent, request: Request):
        query(request)
        media, raw = instance(request, mutation=True)
        return media.begin(raw, request.headers.get("x-csrf-token"), data)

    @router.get("/uploads/{upload_id}", response_model=UploadView)
    def status(upload_id: UUID, request: Request):
        query(request)
        media, raw = instance(request)
        return media.status(raw, upload_id)

    @router.post("/uploads/{upload_id}/content", response_model=UploadView)
    def content(upload_id: UUID, request: Request, data: bytes = Body(media_type="application/octet-stream")):
        query(request)
        media, raw = instance(request, mutation=True, binary=True)
        return media.submit(raw, request.headers.get("x-csrf-token"), upload_id, data)

    @router.post("/uploads/{upload_id}/complete", response_model=UploadView)
    def complete(upload_id: UUID, data: EmptyCommand, request: Request):
        query(request)
        media, raw = instance(request, mutation=True)
        return media.complete(raw, request.headers.get("x-csrf-token"), upload_id)

    @router.post("/uploads/{upload_id}/cancel", response_model=UploadView)
    def cancel(upload_id: UUID, data: EmptyCommand, request: Request):
        query(request)
        media, raw = instance(request, mutation=True)
        return media.cancel(raw, request.headers.get("x-csrf-token"), upload_id)

    @router.get("/assets", response_model=AssetList)
    def assets(request: Request, limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=10000)):
        query(request, ("limit", "offset"))
        media, raw = instance(request)
        return media.list(raw, limit, offset)

    @router.get("/assets/{asset_id}", response_model=AssetView)
    def asset(asset_id: UUID, request: Request):
        query(request)
        media, raw = instance(request)
        return media.get(raw, asset_id)

    @router.post("/assets/{asset_id}/download", response_model=DownloadView)
    def download_ticket(asset_id: UUID, data: EmptyCommand, request: Request):
        query(request)
        media, raw = instance(request, mutation=True)
        return media.ticket(raw, request.headers.get("x-csrf-token"), asset_id)

    @router.get("/assets/{asset_id}/content", response_class=Response,
                responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}})
    def download(asset_id: UUID, request: Request, ticket: str = Query(min_length=43, max_length=43)):
        query(request, ("ticket",))
        media, raw = instance(request)
        data = media.download(raw, asset_id, ticket)
        return Response(data, media_type="image/png", headers={
            "Content-Disposition": f'attachment; filename="{asset_id.hex}.png"',
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox", "Referrer-Policy": "no-referrer"})

    app.include_router(router)
    app.add_middleware(MediaTransportGuard)
