"""Provider credential snapshot and bounded context resolution."""
import sqlalchemy as sa
from cryptography.exceptions import InvalidTag

from . import tables as t
from .credential_crypto import decrypt
from .errors import ChatError
from .schemas import MAX_CONTEXT_CHARS, MAX_CONTEXT_MESSAGES
from .vision import VisionContextMixin


class ExecutionContextMixin(VisionContextMixin):
    def _context_and_key(self, account_id, request_row):
        root = self._root()
        with self.engine.begin() as conn:
            connection = conn.execute(sa.select(t.connections).where(
                t.connections.c.id == request_row["connection_id"],
                t.connections.c.account_id == account_id
            )).mappings().first()
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
                t.messages.c.state == "complete"
            ).order_by(t.messages.c.sequence.desc()).limit(
                MAX_CONTEXT_MESSAGES)).mappings().all()
            message_ids = [item["id"] for item in [*prior, user]]
            grouped = self._vision_rows(
                conn, account_id, message_ids, request_row["model"])
        chosen = self._bounded_context(
            prior, user, grouped, MAX_CONTEXT_CHARS)
        provider = connection["provider"]
        provider_model = self.policy.provider_model(request_row["model"])
        if (not provider_model
                or self.policy.model_provider(request_row["model"]) != provider):
            raise ChatError(503, "model_provider_mismatch")
        return (
            key, provider, provider_model,
            [self._provider_message(item, grouped) for item in chosen],
        )
