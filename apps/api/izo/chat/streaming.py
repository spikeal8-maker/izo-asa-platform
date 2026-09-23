"""SSE claim/follow boundary for durable Chat requests."""
import json
import time
from uuid import UUID
import sqlalchemy as sa
from . import tables as t
from .credentials import ChatError
class StreamingMixin:
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
			row, content = self._snapshot(
				account_id, request_id)
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
			if self.now() > row["deadline_at"] + 5:
				return
			time.sleep(0.2)
