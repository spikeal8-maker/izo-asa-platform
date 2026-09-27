"""DeepSeek adapter with a fixed origin and deterministic test-only transport."""
from __future__ import annotations

import json
import socket
import time
from http.client import HTTPSConnection
from collections.abc import Iterable
from concurrent.futures import Future, TimeoutError as FutureTimeout
from threading import Event, Thread, Timer
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .schemas import MAX_ASSISTANT_CHARS, MAX_SSE_LINE

BASE_URL = "https://api.deepseek.com"
MAX_ERROR_BODY = 64 * 1024

class ProviderFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class _TrackedHTTPS(HTTPSHandler):
    def __init__(self, track, cancelled):
        super().__init__()
        self.track = track
        self.cancelled = cancelled

    def https_open(self, req):
        cancelled = self.cancelled
        class Connection(HTTPSConnection):
            def connect(self):
                if cancelled.is_set():
                    raise TimeoutError()
                super().connect()
                if cancelled.is_set():
                    self.close()
                    raise TimeoutError()
        def connection(host, **kwargs):
            conn = Connection(host, **kwargs)
            self.track(conn)
            return conn
        return self.do_open(connection, req, context=self._context)

def _failure(status: int) -> ProviderFailure:
    return ProviderFailure({
        400: "provider_rejected",
        401: "credential_rejected",
        402: "provider_balance",
        403: "credential_rejected",
        422: "model_rejected",
        429: "provider_rate_limited",
        500: "provider_unavailable",
        503: "provider_overloaded",
    }.get(status, "provider_error"))

class DeepSeekProvider:
    def __init__(self):
        self.opener = build_opener(_NoRedirect)
        self._default_opener = self.opener

    def _open_until(self, request: Request, timeout: float, deadline: float):
        result = Future()
        connection = [None]
        cancelled = Event()
        opener = (build_opener(_NoRedirect, _TrackedHTTPS(
            lambda conn: connection.__setitem__(0, conn), cancelled))
                  if self.opener is self._default_opener else self.opener)

        def open_response() -> None:
            try:
                result.set_result(opener.open(request, timeout=timeout))
            except Exception as exc:
                result.set_exception(exc)

        Thread(target=open_response, daemon=True).start()
        try:
            response = result.result(timeout=max(0, deadline - time.monotonic()))
        except FutureTimeout:
            if time.monotonic() < deadline:
                raise
            cancelled.set()
            conn = connection[0]
            sock = getattr(conn, "sock", None)
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                conn.close()
            elif callable(getattr(opener, "abort", None)):
                opener.abort()
            def close_late(future: Future) -> None:
                try:
                    future.result().close()
                except Exception:
                    pass
            result.add_done_callback(close_late)
            raise ProviderFailure("request_expired") from None
        if time.monotonic() >= deadline:
            response.close()
            raise ProviderFailure("request_expired")
        return response

    def verify(self, key: str, timeout: int = 15) -> None:
        request = Request(BASE_URL + "/models", headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "IZO-ASA/1",
        }, method="GET")
        try:
            with self.opener.open(request, timeout=timeout) as response:
                data = response.read(MAX_ERROR_BODY + 1)
                if response.status != 200 or len(data) > MAX_ERROR_BODY:
                    raise ProviderFailure("credential_check_failed")
                payload = json.loads(data)
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                    raise ProviderFailure("credential_check_failed")
        except HTTPError as exc:
            exc.read(MAX_ERROR_BODY + 1)
            raise _failure(exc.code) from None
        except (URLError, TimeoutError, socket.timeout, OSError, ValueError, json.JSONDecodeError):
            raise ProviderFailure("provider_unavailable") from None

    def stream(self, key: str, model: str, messages: list[dict[str, str]],
               max_tokens: int, timeout: int, stop: Event) -> Iterable[str]:
        if stop.is_set():
            return
        deadline = time.monotonic() + timeout
        expired = Event()
        body = json.dumps({
            "model": model,
            "messages": messages,
            "stream": True,
            "thinking": {"type": "disabled"},
            "max_tokens": max_tokens,
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(BASE_URL + "/chat/completions", data=body, method="POST", headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "IZO-ASA/1",
        })
        total = 0
        finish_reason = None
        try:
            with self._open_until(request, timeout, deadline) as response:
                if response.status != 200:
                    raise _failure(response.status)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderFailure("request_expired")

                def abort_expired() -> None:
                    expired.set()
                    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                    try:
                        if sock is not None:
                            sock.shutdown(socket.SHUT_RDWR)
                        else:
                            response.close()
                    except (OSError, ValueError):
                        pass

                timer = Timer(remaining, abort_expired)
                timer.daemon = True
                timer.start()
                try:
                    while not stop.is_set():
                        if expired.is_set() or time.monotonic() >= deadline:
                            raise ProviderFailure("request_expired")
                        raw = response.readline(MAX_SSE_LINE + 1)
                        if expired.is_set() or time.monotonic() >= deadline:
                            raise ProviderFailure("request_expired")
                        if not raw:
                            raise ProviderFailure("provider_stream_interrupted")
                        if len(raw) > MAX_SSE_LINE:
                            raise ProviderFailure("provider_response_too_large")
                        line = raw.decode("utf-8", "strict").strip()
                        if not line or line.startswith(":") or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            if not total:
                                raise ProviderFailure("provider_empty_response")
                            if finish_reason != "stop":
                                code = ("provider_output_limit" if finish_reason == "length"
                                        else "provider_incomplete_response")
                                raise ProviderFailure(code)
                            return
                        payload = json.loads(data)
                        choices = payload.get("choices") if isinstance(payload, dict) else None
                        choice = choices[0] if isinstance(choices, list) and choices else {}
                        if not isinstance(choice, dict):
                            raise ProviderFailure("provider_invalid_response")
                        finish_reason = choice.get("finish_reason") or finish_reason
                        delta = choice.get("delta", {})
                        text = delta.get("content") if isinstance(delta, dict) else None
                        if not isinstance(text, str) or not text:
                            continue
                        total += len(text)
                        if total > MAX_ASSISTANT_CHARS:
                            raise ProviderFailure("provider_response_too_large")
                        yield text
                    return
                finally:
                    timer.cancel()
        except HTTPError as exc:
            exc.close()
            raise (ProviderFailure("request_expired") if time.monotonic() >= deadline
                   else _failure(exc.code)) from None
        except ProviderFailure:
            raise
        except (URLError, TimeoutError, socket.timeout, OSError, UnicodeError,
                ValueError, json.JSONDecodeError):
            raise ProviderFailure("request_expired" if expired.is_set() or time.monotonic() >= deadline
                                  else "provider_unavailable") from None
