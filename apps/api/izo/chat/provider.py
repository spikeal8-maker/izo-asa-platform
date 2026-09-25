"""Fixed-origin streaming Chat provider adapters."""
from __future__ import annotations

import json
import socket
import time
from collections.abc import Iterable
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .schemas import MAX_ASSISTANT_CHARS, MAX_SSE_LINE

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_ERROR_BODY = 64 * 1024


class ProviderFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _failure(status: int) -> ProviderFailure:
    return ProviderFailure({
        400: "provider_rejected",
        401: "credential_rejected",
        402: "provider_balance",
        403: "credential_rejected",
        422: "model_rejected",
        429: "provider_rate_limited",
        500: "provider_unavailable",
        502: "provider_unavailable",
        503: "provider_overloaded",
        504: "provider_unavailable",
    }.get(status, "provider_error"))


def _verified_json(opener, request: Request, timeout: int, *, require_data_list=False) -> None:
    try:
        with opener.open(request, timeout=timeout) as response:
            data = response.read(MAX_ERROR_BODY + 1)
            if response.status != 200 or len(data) > MAX_ERROR_BODY:
                raise ProviderFailure("credential_check_failed")
            payload = json.loads(data)
            if not isinstance(payload, dict):
                raise ProviderFailure("credential_check_failed")
            if require_data_list and not isinstance(payload.get("data"), list):
                raise ProviderFailure("credential_check_failed")
    except HTTPError as exc:
        exc.read(MAX_ERROR_BODY + 1)
        raise _failure(exc.code) from None
    except ProviderFailure:
        raise
    except (URLError, TimeoutError, socket.timeout, OSError, ValueError, json.JSONDecodeError):
        raise ProviderFailure("provider_unavailable") from None


def _stream_chat(opener, request: Request, timeout: int, stop: Event) -> Iterable[str]:
    total = 0
    finish_reason = None
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise _failure(response.status)
            while not stop.is_set():
                raw = response.readline(MAX_SSE_LINE + 1)
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
    except HTTPError as exc:
        exc.read(MAX_ERROR_BODY + 1)
        raise _failure(exc.code) from None
    except ProviderFailure:
        raise
    except (URLError, TimeoutError, socket.timeout, OSError, UnicodeError,
            ValueError, json.JSONDecodeError):
        raise ProviderFailure("provider_unavailable") from None


class DeepSeekProvider:
    def __init__(self):
        self.opener = build_opener(_NoRedirect)

    def verify(self, key: str, timeout: int = 15) -> None:
        request = Request(DEEPSEEK_BASE_URL + "/models", headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "IZO-ASA/1",
        }, method="GET")
        _verified_json(self.opener, request, timeout, require_data_list=True)

    def stream(self, key: str, model: str, messages: list[dict[str, object]],
               max_tokens: int, timeout: int, stop: Event) -> Iterable[str]:
        if stop.is_set():
            return
        body = json.dumps({
            "model": model,
            "messages": messages,
            "stream": True,
            "thinking": {"type": "disabled"},
            "max_tokens": max_tokens,
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(
            DEEPSEEK_BASE_URL + "/chat/completions", data=body, method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "User-Agent": "IZO-ASA/1",
            })
        yield from _stream_chat(self.opener, request, timeout, stop)


def _fake_text(messages: list[dict[str, object]]) -> tuple[str, str, int]:
    def text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") for part in content
                if isinstance(part, dict) and part.get("type") == "text")
        return ""
    users = [item["content"] for item in messages if item.get("role") == "user"]
    previous = text(users[-2]) if len(users) > 1 else ""
    current = text(users[-1]) if users else ""
    image_count = sum(
        1 for content in users if isinstance(content, list)
        for part in content if isinstance(part, dict)
        and part.get("type") == "image_url")
    return previous, current, image_count


class FakeDeepSeekProvider:
    """CI-only DeepSeek provider; never opens a socket."""
    def verify(self, key: str, timeout: int = 15) -> None:
        if key != "x" * 32:
            raise ProviderFailure("credential_rejected")

    def stream(self, key: str, model: str, messages: list[dict[str, object]],
               max_tokens: int, timeout: int, stop: Event) -> Iterable[str]:
        self.verify(key)
        previous, current, image_count = _fake_text(messages)
        answer = f"Ответ DeepSeek test: {current}" + (
            f" | Контекст: {previous}" if previous else "") + (
            f" | Изображения в контексте: {image_count}" if image_count else "")
        for index in range(0, len(answer), 7):
            if stop.is_set():
                return
            time.sleep(0.01)
            yield answer[index:index + 7]


