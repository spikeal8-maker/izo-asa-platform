"""Bounded urllib transport for fal; network is replaceable in tests."""
import socket
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .fal_core import FalPermanent, HttpResponse, MAX_JSON


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrlLibTransport:
    def __init__(self):
        self.opener = build_opener(_NoRedirect)

    def request(self, method: str, url: str, *, headers: Mapping[str, str] | None = None,
                body: bytes | None = None, timeout: int = 30, maximum: int = MAX_JSON) -> HttpResponse:
        request = Request(url, data=body, headers=dict(headers or {}), method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                data = response.read(maximum + 1)
                if len(data) > maximum:
                    raise FalPermanent("provider_response_too_large")
                return HttpResponse(response.status, dict(response.headers.items()), data)
        except HTTPError as exc:
            data = exc.read(maximum + 1)
            if len(data) > maximum:
                data = b""
            return HttpResponse(exc.code, dict(exc.headers.items()) if exc.headers else {}, data)
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise ConnectionError("provider transport unavailable") from exc
