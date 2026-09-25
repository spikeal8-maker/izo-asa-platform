"""Read-only provider credential views and shared lookup helpers."""
import sqlalchemy as sa

from . import tables as t
from .errors import ChatError
from .schemas import PROVIDERS, CredentialListView, CredentialView


class CredentialReadMixin:
    def _provider_id(self, provider: str) -> str:
        if not self.policy.provider_allowed(provider):
            raise ChatError(404, "provider_not_supported")
        return provider

    @staticmethod
    def _credential_view(row, provider: str = "deepseek") -> CredentialView:
        if not row:
            return CredentialView(
                configured=False, enabled=False, verified=False,
                provider=provider)
        return CredentialView(
            configured=True, enabled=row["enabled"],
            verified=row["verified_at"] is not None,
            revision=row["revision"], generation=row["generation"],
            provider=row["provider"])

    def credentials(self, raw) -> CredentialListView:
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw)
            rows = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"])).mappings().all()
        by_provider = {row["provider"]: row for row in rows}
        return CredentialListView(credentials=[
            self._credential_view(by_provider.get(provider), provider)
            for provider in PROVIDERS
        ])

    def credential(
            self, raw, provider: str = "deepseek") -> CredentialView:
        provider = self._provider_id(provider)
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"],
                t.connections.c.provider == provider)).mappings().first()
            return self._credential_view(row, provider)

    def _root(self) -> bytes:
        try:
            return self.policy.root_key_bytes()
        except RuntimeError:
            raise ChatError(
                503, "credential_storage_unavailable") from None

    @staticmethod
    def _active_for_connection(conn, connection_id) -> bool:
        return conn.execute(sa.select(t.requests.c.id).where(
            t.requests.c.connection_id == connection_id,
            t.requests.c.state.in_(("pending", "streaming"))
        ).limit(1)).first() is not None
