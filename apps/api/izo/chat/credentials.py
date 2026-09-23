"""Account-owned DeepSeek credential lifecycle."""
import hashlib
import hmac
import os
from uuid import UUID, uuid4
import sqlalchemy as sa
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from . import tables as t
from .provider import ProviderFailure
from .schemas import CredentialView
from .schemas import CREDENTIAL_WINDOW_LIMIT
def aad(account_id: UUID, connection_id: UUID, generation: int) -> bytes:
	return f"izo-chat|deepseek|{account_id}|{connection_id}|{generation}".encode("ascii")
def encrypt(root_key: bytes, account_id: UUID, connection_id: UUID,
			generation: int, plaintext: str) -> tuple[bytes, bytes]:
	nonce = os.urandom(12)
	ciphertext = AESGCM(root_key).encrypt(
		nonce, plaintext.encode("utf-8"), aad(account_id, connection_id, generation))
	return nonce, ciphertext
def decrypt(root_key: bytes, account_id: UUID, connection_id: UUID,
			generation: int, nonce: bytes, ciphertext: bytes) -> str:
	value = AESGCM(root_key).decrypt(
		nonce, ciphertext, aad(account_id, connection_id, generation))
	return value.decode("utf-8")
def operation_fingerprint(root_key: bytes, action: str, payload: bytes) -> str:
	return hmac.new(root_key, action.encode("ascii") + b"\0" + payload,
		hashlib.sha256).hexdigest()
class ChatError(Exception):
	def __init__(self, status: int, code: str):
		self.status, self.code = status, code
		super().__init__(code)
class CredentialMixin:
	@staticmethod
	def _credential_view(row) -> CredentialView:
		if not row:
			return CredentialView(configured=False, enabled=False, verified=False)
		return CredentialView(
			configured=True, enabled=row["enabled"],
			verified=row["verified_at"] is not None,
			revision=row["revision"], generation=row["generation"])
	def credential(self, raw) -> CredentialView:
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw)
			row = conn.execute(sa.select(t.connections).where(
				t.connections.c.account_id == account["id"])).mappings().first()
			return self._credential_view(row)
	def _root(self) -> bytes:
		try:
			return self.policy.root_key_bytes()
		except RuntimeError:
			raise ChatError(503, "credential_storage_unavailable") from None
	@staticmethod
	def _active_for_connection(conn, connection_id) -> bool:
		return conn.execute(sa.select(t.requests.c.id).where(
			t.requests.c.connection_id == connection_id,
			t.requests.c.state.in_(("pending", "streaming"))).limit(1)).first() is not None
	def save_credential(self, raw, csrf, command) -> CredentialView:
		root = self._root()
		key = command.key.get_secret_value()
		operation_hash = operation_fingerprint(
			root, "save", (str(command.expected_revision) + "\0" + key).encode("utf-8"))
		now = self.now()
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw, csrf, mutation=True)
			row = conn.execute(sa.select(t.connections).where(
				t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
			if row and row["last_operation_id"] == command.operation_id:
				if row["last_operation_hash"] != operation_hash:
					raise ChatError(409, "operation_conflict")
				return self._credential_view(row)
			self._consume_rate(conn, account["id"], "credential", CREDENTIAL_WINDOW_LIMIT)
			if row and command.expected_revision != row["revision"]:
				raise ChatError(409, "credential_revision_conflict")
			if not row and command.expected_revision is not None:
				raise ChatError(409, "credential_revision_conflict")
			if row and self._active_for_connection(conn, row["id"]):
				raise ChatError(409, "credential_in_use")
			connection_id = row["id"] if row else uuid4()
			generation = row["generation"] + 1 if row else 1
			revision = row["revision"] + 1 if row else 1
			nonce, ciphertext = encrypt(
				root, account["id"], connection_id, generation, key)
			values = dict(
				provider="deepseek", generation=generation, revision=revision,
				nonce=nonce, ciphertext=ciphertext, enabled=True, verified_at=None,
				last_operation_id=command.operation_id,
				last_operation_hash=operation_hash, updated_at=now)
			if row:
				conn.execute(sa.update(t.connections).where(
					t.connections.c.id == connection_id).values(**values))
			else:
				conn.execute(sa.insert(t.connections).values(
					id=connection_id, account_id=account["id"],
					created_at=now, **values))
			return CredentialView(
				configured=True, enabled=True, verified=False,
				revision=revision, generation=generation)
	def verify_credential(self, raw, csrf, command) -> CredentialView:
		root = self._root()
		op_hash = operation_fingerprint(
			root, "verify", f"{command.expected_revision}".encode("ascii"))
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw, csrf, mutation=True)
			row = conn.execute(sa.select(t.connections).where(
				t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
			if not row or not row["enabled"]:
				raise ChatError(409, "credential_not_configured")
			if row["last_operation_id"] == command.operation_id:
				if row["last_operation_hash"] != op_hash:
					raise ChatError(409, "operation_conflict")
				return self._credential_view(row)
			self._consume_rate(conn, account["id"], "credential", CREDENTIAL_WINDOW_LIMIT)
			if row["revision"] != command.expected_revision:
				raise ChatError(409, "credential_revision_conflict")
			snapshot = dict(row)
			try:
				key = decrypt(
					root, account["id"], row["id"], row["generation"],
					row["nonce"], row["ciphertext"])
			except (InvalidTag, UnicodeError, ValueError):
				raise ChatError(503, "credential_unavailable") from None
		try:
			self.provider.verify(
				key, timeout=min(15, self.policy.request_deadline_seconds))
		except ProviderFailure as exc:
			status = 422 if exc.code == "credential_rejected" else 503
			raise ChatError(status, exc.code) from None
		now = self.now()
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw, csrf, mutation=True)
			row = conn.execute(sa.select(t.connections).where(
				t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
			if (not row or row["id"] != snapshot["id"]
					or row["revision"] != snapshot["revision"]
					or row["generation"] != snapshot["generation"]):
				raise ChatError(409, "credential_changed")
			revision = row["revision"] + 1
			conn.execute(sa.update(t.connections).where(
				t.connections.c.id == row["id"]).values(
				verified_at=now, revision=revision, updated_at=now,
				last_operation_id=command.operation_id,
				last_operation_hash=op_hash))
			return CredentialView(
				configured=True, enabled=True, verified=True,
				revision=revision, generation=row["generation"])
	def disable_credential(self, raw, csrf, command) -> CredentialView:
		root = self._root()
		op_hash = operation_fingerprint(
			root, "disable", f"{command.expected_revision}".encode("ascii"))
		now = self.now()
		streaming: list[UUID] = []
		with self.engine.begin() as conn:
			account, _ = self._account(conn, raw, csrf, mutation=True)
			row = conn.execute(sa.select(t.connections).where(
				t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
			if not row:
				raise ChatError(409, "credential_not_configured")
			if row["last_operation_id"] == command.operation_id:
				if row["last_operation_hash"] != op_hash:
					raise ChatError(409, "operation_conflict")
				return self._credential_view(row)
			self._consume_rate(conn, account["id"], "credential", CREDENTIAL_WINDOW_LIMIT)
			if row["revision"] != command.expected_revision:
				raise ChatError(409, "credential_revision_conflict")
			pending = list(conn.execute(sa.select(t.requests.c.id).where(
				t.requests.c.connection_id == row["id"],
				t.requests.c.state == "pending")).scalars())
			streaming = list(conn.execute(sa.select(t.requests.c.id).where(
				t.requests.c.connection_id == row["id"],
				t.requests.c.state == "streaming")).scalars())
			revision = row["revision"] + 1
			conn.execute(sa.update(t.connections).where(
				t.connections.c.id == row["id"]).values(
				enabled=False, verified_at=None, revision=revision, updated_at=now,
				last_operation_id=command.operation_id,
				last_operation_hash=op_hash))
			if pending:
				conn.execute(sa.update(t.requests).where(
					t.requests.c.id.in_(pending)).values(
					state="stopped", stop_requested_at=now, updated_at=now))
				conn.execute(sa.update(t.messages).where(
					t.messages.c.request_id.in_(pending),
					t.messages.c.role == "assistant").values(
					state="stopped", updated_at=now))
			if streaming:
				conn.execute(sa.update(t.requests).where(
					t.requests.c.id.in_(streaming)).values(
					stop_requested_at=now, updated_at=now))
			generation = row["generation"]
		for request_id in streaming:
			self._signal_stop(request_id)
		return CredentialView(
			configured=True, enabled=False, verified=False,
			revision=revision, generation=generation)
