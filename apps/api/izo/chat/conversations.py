"""Durable Thread/Message/Request ownership and idempotency."""
import hashlib
import json
from threading import Event
from uuid import UUID, uuid4
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from . import tables as t
from .credentials import ChatError
from .schemas import MessageView, RequestView, ThreadDetail, ThreadList, ThreadView
from .schemas import MESSAGE_PAGE_LIMIT, MODEL_REVISION, REQUEST_WINDOW_LIMIT, THREAD_PAGE_LIMIT
def _sha(value: dict) -> str:
	raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
	return hashlib.sha256(raw).hexdigest()
class ConversationMixin:
	def create_thread(self, raw, csrf, title: str | None) -> ThreadView:
		now, thread_id = self.now(), uuid4()
		safe = (title or "Новый чат").strip()[:120] or "Новый чат"
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw, csrf, mutation=True)
			conn.execute(sa.insert(t.threads).values(
				id=thread_id, account_id=account["id"], title=safe,
				next_sequence=1, created_at=now, updated_at=now))
		return ThreadView(
			id=thread_id, title=safe, created_at=now, updated_at=now)
	@staticmethod
	def _thread_view(row) -> ThreadView:
		return ThreadView(
			id=row["id"], title=row["title"],
			created_at=row["created_at"], updated_at=row["updated_at"])
	def list_threads(self, raw) -> ThreadList:
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw)
			rows = conn.execute(sa.select(t.threads).where(
				t.threads.c.account_id == account["id"]).order_by(
				t.threads.c.updated_at.desc(), t.threads.c.id.desc()).limit(
				THREAD_PAGE_LIMIT)).mappings().all()
		return ThreadList(threads=[self._thread_view(row) for row in rows])
	@staticmethod
	def _message_view(row) -> MessageView:
		return MessageView(
			id=row["id"], request_id=row["request_id"], role=row["role"],
			sequence=row["sequence"], content=row["content"], state=row["state"],
			created_at=row["created_at"], updated_at=row["updated_at"])
	def thread_detail(self, raw, thread_id: UUID) -> ThreadDetail:
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw)
			thread = conn.execute(sa.select(t.threads).where(
				t.threads.c.id == thread_id,
				t.threads.c.account_id == account["id"])).mappings().first()
			if not thread:
				raise ChatError(404, "thread_not_found")
			rows = conn.execute(sa.select(t.messages).where(
				t.messages.c.thread_id == thread_id).order_by(
				t.messages.c.sequence.desc()).limit(
				MESSAGE_PAGE_LIMIT)).mappings().all()
		return ThreadDetail(
			thread=self._thread_view(thread),
			messages=[self._message_view(row) for row in reversed(rows)])
	@staticmethod
	def _request_view(row) -> RequestView:
		return RequestView(
			id=row["id"], thread_id=row["thread_id"], model=row["model"],
			state=row["state"], error_code=row["error_code"],
			created_at=row["created_at"], updated_at=row["updated_at"],
			deadline_at=row["deadline_at"])
	@staticmethod
	def _request_fingerprint(
			thread_id, text, model, connection_id, generation) -> str:
		return _sha({
			"thread": str(thread_id), "text": text, "model": model,
			"model_revision": MODEL_REVISION,
			"connection": str(connection_id),
			"credential_generation": generation,
		})
	def create_request(self, raw, csrf, thread_id: UUID, command) -> RequestView:
		now = self.now()
		if not self.policy.model_allowed(command.model):
			raise ChatError(422, "model_not_allowed")
		try:
			with self.engine.begin() as conn:
				account, _ = self._account(conn, raw, csrf, mutation=True)
				existing = conn.execute(sa.select(t.requests).where(
					t.requests.c.id == command.request_id)).mappings().first()
				if existing:
					if (existing["account_id"] != account["id"]
							or existing["thread_id"] != thread_id):
						raise ChatError(404, "request_not_found")
					expected = self._request_fingerprint(
						thread_id, command.text, command.model,
						existing["connection_id"],
						existing["credential_generation"])
					if expected != existing["fingerprint"]:
						raise ChatError(409, "request_conflict")
					return self._request_view(existing)
				self._consume_rate(
					conn, account["id"], "request", REQUEST_WINDOW_LIMIT)
				thread = conn.execute(sa.select(t.threads).where(
					t.threads.c.id == thread_id,
					t.threads.c.account_id == account["id"]).with_for_update()).mappings().first()
				if not thread:
					raise ChatError(404, "thread_not_found")
				connection = conn.execute(sa.select(t.connections).where(
					t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
				if (not connection or not connection["enabled"]
						or connection["verified_at"] is None):
					raise ChatError(409, "credential_not_verified")
				fingerprint = self._request_fingerprint(
					thread_id, command.text, command.model,
					connection["id"], connection["generation"])
				request_id = command.request_id
				sequence = thread["next_sequence"]
				conn.execute(sa.insert(t.requests).values(
					id=request_id, thread_id=thread_id,
					account_id=account["id"], fingerprint=fingerprint,
					model=command.model, model_revision=MODEL_REVISION,
					connection_id=connection["id"],
					credential_generation=connection["generation"],
					state="pending", error_code=None, stop_requested_at=None,
					created_at=now, updated_at=now,
					deadline_at=now + self.policy.request_deadline_seconds))
				conn.execute(sa.insert(t.messages), [
					dict(
						id=uuid4(), thread_id=thread_id,
						request_id=request_id, role="user",
						sequence=sequence, part_version=1,
						content=command.text, state="complete",
						created_at=now, updated_at=now),
					dict(
						id=uuid4(), thread_id=thread_id,
						request_id=request_id, role="assistant",
						sequence=sequence + 1, part_version=1,
						content="", state="partial",
						created_at=now, updated_at=now),
				])
				title = thread["title"]
				if sequence == 1 and title == "Новый чат":
					title = command.text.replace("\n", " ").strip()[:72] or title
				conn.execute(sa.update(t.threads).where(
					t.threads.c.id == thread_id).values(
					next_sequence=sequence + 2,
					title=title, updated_at=now))
				row = conn.execute(sa.select(t.requests).where(
					t.requests.c.id == request_id)).mappings().one()
				return self._request_view(row)
		except IntegrityError as exc:
			raise ChatError(409, "active_request_exists") from exc
	def request(self, raw, request_id: UUID) -> RequestView:
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw)
			row = conn.execute(sa.select(t.requests).where(
				t.requests.c.id == request_id,
				t.requests.c.account_id == account["id"])).mappings().first()
			if not row:
				raise ChatError(404, "request_not_found")
			return self._request_view(row)
	def stop(self, raw, csrf, request_id: UUID) -> RequestView:
		now = self.now()
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw, csrf, mutation=True)
			row = conn.execute(sa.select(t.requests).where(
				t.requests.c.id == request_id,
				t.requests.c.account_id == account["id"]).with_for_update()).mappings().first()
			if not row:
				raise ChatError(404, "request_not_found")
			if row["state"] in {
					"completed", "interrupted", "error", "stopped"}:
				return self._request_view(row)
			if row["state"] == "pending":
				conn.execute(sa.update(t.requests).where(
					t.requests.c.id == request_id).values(
					state="stopped", stop_requested_at=now, updated_at=now))
				conn.execute(sa.update(t.messages).where(
					t.messages.c.request_id == request_id,
					t.messages.c.role == "assistant").values(
					state="stopped", updated_at=now))
			else:
				conn.execute(sa.update(t.requests).where(
					t.requests.c.id == request_id).values(
					stop_requested_at=now, updated_at=now))
		self._signal_stop(request_id)
		return self.request(raw, request_id)
	def _signal_stop(self, request_id: UUID) -> None:
		with self._stop_lock:
			event = self._stops.get(request_id)
			if event:
				event.set()
	def _register_stop(self, request_id: UUID) -> Event:
		with self._stop_lock:
			event = self._stops.setdefault(request_id, Event())
		with self.engine.begin() as conn:
			requested = conn.execute(sa.select(t.requests.c.stop_requested_at).where(
				t.requests.c.id == request_id)).scalar_one()
		if requested is not None:
			event.set()
		return event
	def _unregister_stop(self, request_id: UUID) -> None:
		with self._stop_lock:
			self._stops.pop(request_id, None)
