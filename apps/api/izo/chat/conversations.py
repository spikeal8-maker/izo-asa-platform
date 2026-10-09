"""Durable Thread/Message/Request ownership and idempotency."""
from uuid import UUID, uuid4
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from . import tables as t
from .attachments import AttachmentMixin
from .credentials import ChatError
from .history_pages import older_messages, thread_detail
from .thread_pages import list_threads, thread_view
from .request_state import RequestStateMixin, UNKNOWN_PAID_OUTCOME
from .schemas import MessageView, RequestView, ThreadDetail, ThreadList, ThreadView
from .schemas import MODEL_REVISION, REQUEST_WINDOW_LIMIT
from .schemas import OPENROUTER_AUTO_MODEL
class ConversationMixin(AttachmentMixin, RequestStateMixin):
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
		return thread_view(row)
	def list_threads(self, raw, cursor: str | None = None) -> ThreadList:
		return list_threads(self, raw, cursor)
	@classmethod
	def _message_view(cls, row, attachment_rows=()) -> MessageView:
		return MessageView(
			id=row["id"], request_id=row["request_id"], role=row["role"],
			sequence=row["sequence"], content=row["content"], state=row["state"],
			attachments=[cls._attachment_view(item) for item in attachment_rows],
			created_at=row["created_at"], updated_at=row["updated_at"])
	def thread_detail(self, raw, thread_id: UUID) -> ThreadDetail:
		return thread_detail(self, raw, thread_id)
	def older_messages(self, raw, thread_id: UUID, before_sequence: int):
		return older_messages(self, raw, thread_id, before_sequence)
	def create_request(self, raw, csrf, thread_id: UUID, command) -> RequestView:
		# Resolve remote catalog IDs before acquiring the thread row lock. Durable
		# request replays still work when the provider catalog is unavailable.
		dynamic_provider, dynamic_vision = None, False
		if "/" in command.model:
			with self.engine.begin() as conn:
				account, _ = self._account(conn, raw, csrf, mutation=True)
				exists = conn.execute(sa.select(t.requests.c.id).where(
					t.requests.c.id == command.request_id,
					t.requests.c.account_id == account["id"],
					t.requests.c.thread_id == thread_id)).first() is not None
				if not exists and conn.execute(sa.select(t.requests.c.id).where(
						t.requests.c.account_id == account["id"],
						t.requests.c.thread_id == thread_id,
						t.requests.c.error_code == UNKNOWN_PAID_OUTCOME
					).limit(1)).first():
					raise ChatError(409, UNKNOWN_PAID_OUTCOME)
			if not exists:
				dynamic_provider, _, dynamic_vision = self.model_admission(command.model)
		try:
			with self.engine.begin() as conn:
				account, _ = self._account(conn, raw, csrf, mutation=True)
				thread = conn.execute(sa.select(t.threads).where(
					t.threads.c.id == thread_id,
					t.threads.c.account_id == account["id"]).with_for_update()).mappings().first()
				if not thread:
					raise ChatError(404, "thread_not_found")
				now = self.now()
				expired = conn.execute(sa.update(t.requests).where(
					t.requests.c.thread_id == thread_id,
					t.requests.c.state == "pending",
					t.requests.c.deadline_at <= now).values(
					state="interrupted", error_code="request_expired",
					updated_at=now).returning(t.requests.c.id)).scalars().all()
				if expired:
					conn.execute(sa.update(t.messages).where(
						t.messages.c.request_id.in_(expired),
						t.messages.c.role == "assistant").values(
						state="interrupted", updated_at=now))
			with self.engine.begin() as conn:
				account, _ = self._account(conn, raw, csrf, mutation=True)
				thread = conn.execute(sa.select(t.threads).where(
					t.threads.c.id == thread_id,
					t.threads.c.account_id == account["id"]).with_for_update()).mappings().first()
				if not thread:
					raise ChatError(404, "thread_not_found")
				now = self.now()
				existing = conn.execute(sa.select(t.requests).where(
					t.requests.c.id == command.request_id)).mappings().first()
				if existing:
					if (existing["account_id"] != account["id"]
							or existing["thread_id"] != thread_id):
						raise ChatError(404, "request_not_found")
					expected = self._request_fingerprint(
						thread_id, command.text, command.model,
					existing["connection_id"],
					existing["credential_generation"], existing["model_revision"],
					command.attachment_ids)
					if expected != existing["fingerprint"]:
						raise ChatError(409, "request_conflict")
					return self._request_view(existing)
				if conn.execute(sa.select(t.requests.c.id).where(
						t.requests.c.thread_id == thread_id,
						t.requests.c.account_id == account["id"],
						t.requests.c.error_code == UNKNOWN_PAID_OUTCOME
					).limit(1)).first():
					raise ChatError(409, UNKNOWN_PAID_OUTCOME)
				head, allowed_models = self.catalog.public_text(conn, lock=True)
				if command.model == OPENROUTER_AUTO_MODEL:
					provider = "openrouter"
					vision = False
				elif "/" in command.model:
					if dynamic_provider is None:
						raise ChatError(409, "request_conflict")
					provider = dynamic_provider
					vision = dynamic_vision
				else:
					selected = next((item for item in allowed_models
					                 if item.id == command.model), None)
					if selected is None:
						raise ChatError(422, "model_not_allowed")
					provider = selected.provider
					vision = self.static_vision_supported(selected.id, provider)
				if command.attachment_ids and not vision:
					raise ChatError(422, "model_vision_unsupported")
				assets = self._attachment_assets(conn, account["id"], command.attachment_ids)
				self._consume_rate(
					conn, account["id"], "request", REQUEST_WINDOW_LIMIT)
				connection = conn.execute(sa.select(t.connections).where(
					t.connections.c.account_id == account["id"],
					t.connections.c.provider == provider
				).with_for_update()).mappings().first()
				if (not connection or not connection["enabled"]
						or connection["verified_at"] is None):
					raise ChatError(409, "credential_not_verified")
				model_revision = (f"{MODEL_REVISION}:catalog-{head['revision']}"
				                  if provider == "deepseek" else
				                  f"{MODEL_REVISION}:openrouter")
				fingerprint = self._request_fingerprint(
					thread_id, command.text, command.model,
					connection["id"], connection["generation"], model_revision,
					command.attachment_ids)
				request_id = command.request_id
				sequence = thread["next_sequence"]
				user_message_id, assistant_message_id = uuid4(), uuid4()
				conn.execute(sa.insert(t.requests).values(
					id=request_id, thread_id=thread_id,
					account_id=account["id"], fingerprint=fingerprint,
					model=command.model, model_revision=model_revision,
					connection_id=connection["id"],
					credential_generation=connection["generation"],
					vision_admitted=vision,
					state="pending", error_code=None, stop_requested_at=None,
					created_at=now, updated_at=now,
					deadline_at=now + self.policy.request_deadline_seconds))
				conn.execute(sa.insert(t.messages), [
					dict(
						id=user_message_id, thread_id=thread_id,
						request_id=request_id, role="user",
						sequence=sequence, part_version=1,
						content=command.text, state="complete",
						created_at=now, updated_at=now),
					dict(
						id=assistant_message_id, thread_id=thread_id,
						request_id=request_id, role="assistant",
						sequence=sequence + 1, part_version=1,
						content="", state="partial",
						created_at=now, updated_at=now),
				])
				self._insert_attachments(conn, account["id"], request_id,
				                         user_message_id, assets, now)
				title = thread["title"]
				if sequence == 1 and title == "Новый чат":
					title = command.text.replace("\n", " ").strip()[:72] or "Изображение"
				conn.execute(sa.update(t.threads).where(
					t.threads.c.id == thread_id).values(
					next_sequence=sequence + 2,
					title=title, updated_at=now))
				row = conn.execute(sa.select(t.requests).where(
					t.requests.c.id == request_id)).mappings().one()
				return self._request_view(row)
		except IntegrityError as exc:
			raise ChatError(409, "active_request_exists") from exc
