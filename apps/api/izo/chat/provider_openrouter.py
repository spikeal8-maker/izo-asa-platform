"""Fixed-origin OpenRouter BYOK streaming provider."""
import json
import time
from collections.abc import Iterable
from threading import Event
from urllib.request import Request, build_opener

from .provider import (
    ProviderFailure, _NoRedirect, _fake_text, _stream_chat, _verified_json,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider:
    """OpenRouter BYOK adapter; endpoint selection is never client-controlled."""
    def __init__(self):
        self.opener = build_opener(_NoRedirect)

    def verify(self, key: str, timeout: int = 15) -> None:
        request = Request(OPENROUTER_BASE_URL + "/key", headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "IZO-ASA/1",
            "X-Title": "IZO ASA",
        }, method="GET")
        _verified_json(self.opener, request, timeout)

    def stream(self, key: str, model: str, messages: list[dict[str, object]],
               max_tokens: int, timeout: int, stop: Event) -> Iterable[str]:
        if stop.is_set():
            return
        body = json.dumps({
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(
            OPENROUTER_BASE_URL + "/chat/completions", data=body, method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "User-Agent": "IZO-ASA/1",
                "X-Title": "IZO ASA",
            })
        yield from _stream_chat(self.opener, request, timeout, stop)


class FakeOpenRouterProvider:
    """CI-only OpenRouter provider; never opens a socket."""
    TEST_KEY = "or-" + "x" * 32

    def verify(self, key: str, timeout: int = 15) -> None:
        if key != self.TEST_KEY:
            raise ProviderFailure("credential_rejected")

    def stream(self, key: str, model: str, messages: list[dict[str, object]],
               max_tokens: int, timeout: int, stop: Event) -> Iterable[str]:
        self.verify(key)
        previous, current, _ = _fake_text(messages)
        answer = f"Ответ OpenRouter test: {current}" + (
            f" | Контекст: {previous}" if previous else "")
        for index in range(0, len(answer), 7):
            if stop.is_set():
                return
            time.sleep(0.01)
            yield answer[index:index + 7]
