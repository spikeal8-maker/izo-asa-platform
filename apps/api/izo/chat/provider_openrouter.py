"""Fixed-origin OpenRouter BYOK adapter with the shared bounded stream transport."""
import json
import socket
import time
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .provider import DeepSeekProvider, MAX_ERROR_BODY, ProviderFailure, _failure

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(DeepSeekProvider):
    def verify(self, key: str, timeout: int = 15) -> None:
        request = Request(OPENROUTER_BASE_URL + "/key", headers={
            "Authorization": f"Bearer {key}", "Accept": "application/json",
            "User-Agent": "IZO-ASA/1", "X-Title": "IZO ASA",
        }, method="GET")
        try:
            with self.opener.open(request, timeout=timeout) as response:
                data = response.read(MAX_ERROR_BODY + 1)
                if response.status != 200 or len(data) > MAX_ERROR_BODY:
                    raise ProviderFailure("credential_check_failed")
                if not isinstance(json.loads(data), dict):
                    raise ProviderFailure("credential_check_failed")
        except HTTPError as exc:
            exc.read(MAX_ERROR_BODY + 1)
            raise _failure(exc.code) from None
        except ProviderFailure:
            raise
        except (URLError, TimeoutError, socket.timeout, OSError,
                ValueError, UnicodeError):
            raise ProviderFailure("provider_unavailable") from None

    @staticmethod
    def _chat_request(key: str, model: str, messages: list[dict], max_tokens: int) -> Request:
        body = json.dumps({
            "model": model, "messages": messages, "stream": True,
            "max_tokens": max_tokens,
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return Request(OPENROUTER_BASE_URL + "/chat/completions", data=body,
                       method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "Accept": "text/event-stream", "User-Agent": "IZO-ASA/1",
            "X-Title": "IZO ASA",
        })


class FakeOpenRouterProvider:
    """Deterministic isolated-test provider. Never opens a socket."""
    TEST_KEY = "or-" + "x" * 32

    def verify(self, key: str, timeout: int = 15) -> None:
        if key != self.TEST_KEY:
            raise ProviderFailure("credential_rejected")

    def stream(self, key: str, model: str, messages: list[dict],
               max_tokens: int, timeout: int, stop: Event):
        self.verify(key)
        users = [item["content"] for item in messages if item.get("role") == "user"]
        answer = f"Ответ OpenRouter test: {users[-1] if users else ''}"
        for index in range(0, len(answer), 7):
            if stop.is_set():
                return
            time.sleep(0.01)
            yield answer[index:index + 7]
