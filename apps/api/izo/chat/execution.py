"""Outbound execution and durable partial/final persistence."""
import json
import time
from contextlib import closing
from collections.abc import Iterable
from threading import Event
from uuid import UUID
import sqlalchemy as sa
from cryptography.exceptions import InvalidTag
from . import tables as t
from .credentials import ChatError, decrypt
from .provider import ProviderFailure
from .request_state import KNOWN_PROVIDER_REJECTIONS, UNKNOWN_PAID_OUTCOME
from .schemas import MAX_CONTEXT_CHARS, MAX_CONTEXT_MESSAGES, MAX_OUTPUT_TOKENS, OPENROUTER_AUTO_MODEL
from .vision import VisionContextMixin

RUSSIAN_REPLY_PREFERENCE = (
    "Отвечай на русском языке, если пользователь явно не попросил другой язык. "
    "Сохраняй исходный язык кода, цитат и имён собственных."
)
class ExecutionMixin(VisionContextMixin):
	def _context_and_key(self, account_id, request_row):
		root = self._root()
		with self.engine.begin() as conn:
			connection = conn.execute(sa.select(t.connections).where(
				t.connections.c.id == request_row["connection_id"],
				t.connections.c.account_id == account_id)).mappings().first()
			if (not connection or not connection["enabled"]
					or connection["generation"]
					!= request_row["credential_generation"]):
				raise ChatError(503, "credential_unavailable")
			try:
				key = decrypt(
					root, account_id, connection["id"],
					connection["generation"], connection["nonce"],
					connection["ciphertext"], connection["provider"])
			except (InvalidTag, UnicodeError, ValueError):
				raise ChatError(503, "credential_unavailable") from None
			user = conn.execute(sa.select(t.messages).where(
				t.messages.c.request_id == request_row["id"],
				t.messages.c.role == "user")).mappings().one()
			prior = conn.execute(sa.select(t.messages).where(
				t.messages.c.thread_id == request_row["thread_id"],
				t.messages.c.sequence < user["sequence"],
				t.messages.c.state == "complete").order_by(
				t.messages.c.sequence.desc()).limit(
				MAX_CONTEXT_MESSAGES)).mappings().all()
			grouped = (self._vision_rows(conn, account_id,
				[item["id"] for item in [*prior, user]])
				if request_row["vision_admitted"] else {})
		chosen = self._bounded_context(prior, user, grouped, MAX_CONTEXT_CHARS)
		provider = connection["provider"]
		if request_row["model"] == OPENROUTER_AUTO_MODEL:
			resolved_provider, provider_model = "openrouter", "openrouter/auto"
		elif "/" in request_row["model"]:
			resolved_provider, provider_model = "openrouter", request_row["model"]
		else:
			resolved_provider, provider_model = "deepseek", request_row["model"]
		if provider != resolved_provider:
			raise ChatError(503, "model_provider_mismatch")
		messages = [{"role": "system", "content": RUSSIAN_REPLY_PREFERENCE}]
		messages.extend(self._provider_message(item, grouped) for item in chosen)
		return key, provider, provider_model, messages
	def _save_partial(self, request_id, content: str) -> None:
		now = self.now()
		with self.engine.begin() as conn:
			state = conn.execute(sa.select(t.requests.c.state).where(
				t.requests.c.id == request_id)).scalar_one_or_none()
			if state != "streaming":
				return
			conn.execute(sa.update(t.messages).where(
				t.messages.c.request_id == request_id,
				t.messages.c.role == "assistant").values(
				content=content, state="partial", updated_at=now))
			conn.execute(sa.update(t.requests).where(
				t.requests.c.id == request_id).values(updated_at=now))
	def _execute(self, account_id, request_row):
		request_id = request_row["id"]
		event = self._register_stop(request_id)
		content, saved_at, saved_len = "", time.monotonic(), 0
		sequence = 0
		provider = None
		submitted = False
		try:
			yield self._event(
				"message.start",
				{"request_id": str(request_id), "sequence": sequence})
			key, provider, provider_model, messages = self._context_and_key(
				account_id, request_row)
			remaining = request_row["deadline_at"] - self.now()
			if remaining <= 0:
				raise ProviderFailure("request_expired")
			adapter = self.provider_for(provider)
			# Commit the durable paid-outcome marker before either provider POST.
			self._mark_paid_submission(request_id)
			submitted = True
			expired = False
			with closing(adapter.stream(
					key, provider_model, messages, MAX_OUTPUT_TOKENS, remaining, event)) as source:
				for chunk in source:
					if self.now() >= request_row["deadline_at"]:
						expired = True
						break
					if event.is_set():
						break
					content += chunk
					sequence += 1
					yield self._event(
						"text.delta", {
							"request_id": str(request_id),
							"sequence": sequence,
							"text": chunk,
						})
					current = time.monotonic()
					if (len(content) - saved_len >= 512
							or current - saved_at >= 0.5):
						self._save_partial(request_id, content)
						saved_len, saved_at = len(content), current
			state = self._finish(request_id,
				"interrupted" if expired else "stopped" if event.is_set() else "completed",
				"request_expired" if expired else None, content)
			sequence += 1
			payload = {"request_id": str(request_id), "sequence": sequence}
			if state == "completed":
				payload["text_length"] = len(content)
			else:
				payload["reason"] = state
				if submitted:
					row, _ = self._snapshot(account_id, request_id)
					if row["error_code"] == UNKNOWN_PAID_OUTCOME:
						payload["code"] = UNKNOWN_PAID_OUTCOME
			yield self._event("message.done" if state == "completed"
				else "message.interrupted", payload)
		except (ChatError, ProviderFailure) as exc:
			code = (UNKNOWN_PAID_OUTCOME if submitted
					and exc.code not in KNOWN_PROVIDER_REJECTIONS else exc.code)
			state = self._finish(request_id,
				"interrupted" if exc.code == "request_expired" else "error",
				code, content)
			sequence += 1
			payload = {"request_id": str(request_id), "sequence": sequence}
			interrupted = state in {"interrupted", "stopped"}
			payload["reason" if interrupted else "code"] = state if interrupted else code
			if interrupted and code == UNKNOWN_PAID_OUTCOME:
				payload["code"] = code
			yield self._event("message.interrupted" if interrupted else "message.error", payload)
		except GeneratorExit:
			self._finish(
				request_id, "interrupted",
				"client_disconnected", content)
			raise
		except Exception:
			code = UNKNOWN_PAID_OUTCOME if submitted else "chat_execution_failed"
			self._finish(
				request_id, "error",
				code, content)
			sequence += 1
			yield self._event(
				"message.error", {
					"request_id": str(request_id),
					"sequence": sequence,
					"code": code,
				})
		finally:
			self._unregister_stop(request_id)
	def stream_events(self, raw, request_id: UUID):
		execute = False
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw)
			row = conn.execute(sa.select(t.requests).where(
				t.requests.c.id == request_id,
				t.requests.c.account_id == account["id"]).with_for_update()).mappings().first()
			if not row:
				raise ChatError(404, "request_not_found")
			now = self.now()
			if row["state"] == "pending":
				if row["deadline_at"] <= now:
					self._terminal(
						conn, request_id, "interrupted",
						"request_expired", now)
					row = conn.execute(sa.select(t.requests).where(
						t.requests.c.id == request_id)).mappings().one()
				else:
					conn.execute(sa.update(t.requests).where(
						t.requests.c.id == request_id,
						t.requests.c.state == "pending").values(
						state="streaming", updated_at=now))
					execute = True
					row = dict(row)
					row["state"] = "streaming"
			account_id = account["id"]
		if execute:
			return self._execute(account_id, dict(row))
		return self._follow(account_id, request_id)
	@staticmethod
	def _event(name: str, payload: dict) -> str:
		return (
			f"event: {name}\n"
			f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
		)

class FakeDeepSeekProvider:
    """CI-only provider. It never opens a socket and exposes deterministic chunks."""
    def verify(self, key: str, timeout: int = 15) -> None:
        if key != "x" * 32:
            raise ProviderFailure("credential_rejected")

    def stream(self, key: str, model: str, messages: list[dict[str, str]],
               max_tokens: int, timeout: int, stop: Event) -> Iterable[str]:
        self.verify(key)
        def visible_text(content):
            if isinstance(content, str):
                return content
            return " ".join(part.get("text", "") for part in content
                            if part.get("type") == "text")
        users = [visible_text(item["content"]) for item in messages
                 if item.get("role") == "user"]
        previous = users[-2] if len(users) > 1 else ""
        current = users[-1] if users else ""
        answer = f"Ответ DeepSeek test: {current}" + (
            f" | Контекст: {previous}" if previous else "")
        for index in range(0, len(answer), 7):
            if stop.is_set():
                return
            time.sleep(0.01)
            yield answer[index:index + 7]
