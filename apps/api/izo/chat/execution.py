"""Outbound execution and durable partial/final persistence."""
import json
import time
from uuid import UUID
import sqlalchemy as sa
from cryptography.exceptions import InvalidTag
from . import tables as t
from .credentials import ChatError, decrypt
from .provider import ProviderFailure
from .schemas import MAX_CONTEXT_CHARS, MAX_CONTEXT_MESSAGES, MAX_OUTPUT_TOKENS
from .vision import VisionContextMixin
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
					connection["ciphertext"])
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
			message_ids = [item["id"] for item in [*prior, user]]
			grouped = self._vision_rows(
				conn, account_id, message_ids, request_row["model"])
		chosen = self._bounded_context(
			prior, user, grouped, MAX_CONTEXT_CHARS)
		return key, [self._provider_message(item, grouped) for item in chosen]
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
	def _terminal(
			self, conn, request_id, state: str,
			error_code: str | None, now: int,
			content: str | None = None) -> None:
		conn.execute(sa.update(t.requests).where(
			t.requests.c.id == request_id).values(
			state=state, error_code=error_code, updated_at=now))
		message_state = "complete" if state == "completed" else state
		values = {"state": message_state, "updated_at": now}
		if content is not None:
			values["content"] = content
		conn.execute(sa.update(t.messages).where(
			t.messages.c.request_id == request_id,
			t.messages.c.role == "assistant").values(**values))
		thread_id = conn.execute(sa.select(t.requests.c.thread_id).where(
			t.requests.c.id == request_id)).scalar_one()
		conn.execute(sa.update(t.threads).where(
			t.threads.c.id == thread_id).values(updated_at=now))
	def _finish(self, request_id, state, error_code, content):
		now = self.now()
		with self.engine.begin() as conn:
			current, stopped_at, deadline = conn.execute(sa.select(
				t.requests.c.state, t.requests.c.stop_requested_at, t.requests.c.deadline_at
			).where(t.requests.c.id == request_id).with_for_update()).one()
			if current in {"completed", "interrupted", "error", "stopped"}:
				return current
			if stopped_at is not None:
				state, error_code = "stopped", None
			elif state == "completed" and now >= deadline:
				state, error_code = "interrupted", "request_expired"
			self._terminal(
				conn, request_id, state, error_code, now, content)
		if state != "completed":
			self._signal_stop(request_id)
		return state
	def _execute(self, account_id, request_row):
		request_id = request_row["id"]
		event = self._register_stop(request_id)
		content, saved_at, saved_len = "", time.monotonic(), 0
		sequence = 0
		try:
			yield self._event(
				"message.start",
				{"request_id": str(request_id), "sequence": sequence})
			key, messages = self._context_and_key(
				account_id, request_row)
			remaining = request_row["deadline_at"] - self.now()
			if remaining <= 0:
				raise ProviderFailure("request_expired")
			for chunk in self.provider.stream(
					key, request_row["model"], messages, MAX_OUTPUT_TOKENS, remaining, event):
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
				"stopped" if event.is_set() else "completed", None, content)
			sequence += 1
			payload = {"request_id": str(request_id), "sequence": sequence}
			if state == "completed":
				payload["text_length"] = len(content)
			else:
				payload["reason"] = state
			yield self._event("message.done" if state == "completed"
				else "message.interrupted", payload)
		except (ChatError, ProviderFailure) as exc:
			self._finish(request_id, "error", exc.code, content)
			sequence += 1
			yield self._event(
				"message.error", {
					"request_id": str(request_id),
					"sequence": sequence,
					"code": exc.code,
				})
		except GeneratorExit:
			self._finish(
				request_id, "interrupted",
				"client_disconnected", content)
			raise
		except Exception:
			self._finish(
				request_id, "error",
				"chat_execution_failed", content)
			sequence += 1
			yield self._event(
				"message.error", {
					"request_id": str(request_id),
					"sequence": sequence,
					"code": "chat_execution_failed",
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
	def _snapshot(self, account_id, request_id):
		with self.engine.begin() as conn:
			row = conn.execute(sa.select(t.requests).where(
				t.requests.c.id == request_id,
				t.requests.c.account_id == account_id)).mappings().first()
			if not row:
				raise ChatError(404, "request_not_found")
			assistant = conn.execute(sa.select(
				t.messages.c.content).where(
				t.messages.c.request_id == request_id,
				t.messages.c.role == "assistant")).scalar_one()
			return dict(row), assistant
	def _follow(self, account_id, request_id):
		sent, sequence = 0, 0
		yield self._event(
			"message.start", {
				"request_id": str(request_id),
				"sequence": sequence,
			})
		while True:
			row, content = self._snapshot(account_id, request_id)
			if row["state"] in {"pending", "streaming"} and (
					row["stop_requested_at"] is not None or self.now() >= row["deadline_at"]):
				stopped = row["stop_requested_at"] is not None
				self._finish(request_id, "stopped" if stopped else "interrupted",
					None if stopped else "request_expired", content)
				continue
			if len(content) > sent:
				sequence += 1
				yield self._event(
					"text.delta", {
						"request_id": str(request_id),
						"sequence": sequence,
						"text": content[sent:],
					})
				sent = len(content)
			state = row["state"]
			if state == "completed":
				sequence += 1
				yield self._event(
					"message.done", {
						"request_id": str(request_id),
						"sequence": sequence,
						"text_length": len(content),
					})
				return
			if state in {"interrupted", "stopped"}:
				sequence += 1
				yield self._event(
					"message.interrupted", {
						"request_id": str(request_id),
						"sequence": sequence,
						"reason": state,
					})
				return
			if state == "error":
				sequence += 1
				yield self._event(
					"message.error", {
						"request_id": str(request_id),
						"sequence": sequence,
						"code": row["error_code"] or "chat_execution_failed",
					})
				return
			time.sleep(0.2)
