"""Versioned catalog lifecycle; offline proof cannot activate spend."""
import hmac
from uuid import uuid4

import sqlalchemy as sa
from ..accounts.admin_access import staff_session
from ..accounts.security import AuthError, verify_password
from ..providers.openrouter.client import ENDPOINT
from . import repository as repo, tables as t
from .schemas import (CapabilityContent, CapabilityDraft, CapabilityList, CatalogError,
    ConnectionContent, ConnectionDraft, ConnectionList, CredentialBind, DisableInput,
    ProofInput, ProofView, ProviderList, PublishInput, RevokeCredential)

ADAPTER = "openrouter.images.v1"
PROVIDER = "openrouter"


class CatalogService:
    def __init__(self, auth):
        self.auth = auth

    @staticmethod
    def _cap_content(data: CapabilityDraft) -> CapabilityContent:
        return CapabilityContent(name=data.name, help=data.help, adapter_id=data.adapter_id,
            model_id=data.model_id, connection_id=data.connection_id,
            resolutions=data.resolutions, price_credits=data.price_credits)

    @staticmethod
    def _conn_content(data: ConnectionDraft) -> ConnectionContent:
        return ConnectionContent(provider_id=PROVIDER, endpoint=ENDPOINT, account_ref=data.account_ref,
            project_ref=data.project_ref, environment=data.environment, max_concurrency=data.max_concurrency,
            rate_limit=data.rate_limit, rate_window_seconds=data.rate_window_seconds,
            spend_cap_minor=data.spend_cap_minor, currency=data.currency,
            timeout_seconds=data.timeout_seconds, allow_fallbacks=data.allow_fallbacks)


    def providers(self, raw):
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"connections.read"})
            return ProviderList()

    def capabilities(self, raw):
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"catalog.read"})
            ids = conn.execute(sa.select(t.capability_heads.c.capability_id).order_by(t.capability_heads.c.capability_id)).scalars().all()
            return CapabilityList(items=tuple(repo.capability_view(conn, value) for value in ids))

    def capability(self, raw, capability_id):
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"catalog.read"})
            return repo.capability_view(conn, capability_id)

    def connections(self, raw):
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"connections.read"})
            ids = conn.execute(sa.select(t.connection_heads.c.connection_id).order_by(t.connection_heads.c.connection_id)).scalars().all()
            return ConnectionList(items=tuple(repo.connection_view(conn, value) for value in ids))

    def connection(self, raw, connection_id):
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"connections.read"})
            return repo.connection_view(conn, connection_id)

    def credential(self, raw, connection_id):
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"connections.read", "secrets.bind"})
            if not repo.head(conn, t.connection_heads, t.connection_heads.c.connection_id, connection_id):
                raise CatalogError(404, "not_found")
            row = repo.active_credential(conn, connection_id)
            if not row:
                raise CatalogError(404, "credential_unavailable")
            return repo.credential_view(row)

    def save_capability(self, raw, csrf, capability_id, data: CapabilityDraft):
        data = CapabilityDraft.model_validate(data)
        if capability_id != capability_id.lower() or not __import__('re').fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", capability_id):
            raise CatalogError(422, "invalid_capability")
        with self.auth.engine.begin() as conn:
            actor, _, _ = staff_session(self.auth, conn, raw, {"catalog.write", "pricing.write"}, csrf=csrf, mutation=True)
            return repo.save_revision(conn, now=self.auth.now(), actor=actor["id"], operation_id=data.operation_id,
                expected_version=data.expected_version, target=capability_id, reason=data.reason,
                head_table=t.capability_heads, revision_table=t.capability_revisions,
                key_col=t.capability_heads.c.capability_id, content=self._cap_content(data), action="capability.draft")

    def save_connection(self, raw, csrf, connection_id, data: ConnectionDraft):
        data = ConnectionDraft.model_validate(data)
        if connection_id != connection_id.lower() or not __import__('re').fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,79}", connection_id):
            raise CatalogError(422, "invalid_connection")
        with self.auth.engine.begin() as conn:
            actor, _, _ = staff_session(self.auth, conn, raw, {"connections.write"}, csrf=csrf, mutation=True)
            return repo.save_revision(conn, now=self.auth.now(), actor=actor["id"], operation_id=data.operation_id,
                expected_version=data.expected_version, target=connection_id, reason=data.reason,
                head_table=t.connection_heads, revision_table=t.connection_revisions,
                key_col=t.connection_heads.c.connection_id, content=self._conn_content(data), action="connection.draft")

    def _password_proof(self, raw, csrf, current_password, peer, required):
        with self.auth.engine.begin() as conn:
            account, _, _ = staff_session(self.auth, conn, raw, required, csrf=csrf, mutation=True)
            owner, encoded = account["id"], account["password_hash"]
        self.auth.throttle("catalog-secret:" + str(owner), peer)
        if not verify_password(current_password.get_secret_value(), encoded):
            raise AuthError(403, "reauth_required")
        return owner, encoded

    def bind_credential(self, raw, csrf, connection_id, data: CredentialBind, peer="catalog"):
        data = CredentialBind.model_validate(data)
        owner, encoded = self._password_proof(raw, csrf, data.current_password, peer,
            {"connections.write", "secrets.bind"})
        safe = data.model_dump(mode="json", exclude={"current_password"})
        fp = repo.fingerprint("credential.bind", owner, connection_id, safe)
        with self.auth.engine.begin() as conn:
            actor, _, _ = staff_session(self.auth, conn, raw, {"connections.write", "secrets.bind"}, csrf=csrf, mutation=True)
            if actor["id"] != owner or not hmac.compare_digest(actor["password_hash"], encoded):
                raise AuthError(403, "reauth_required")
            old = repo.replay(conn, data.operation_id, fp)
            if old:
                row = conn.execute(sa.select(t.credential_bindings).where(t.credential_bindings.c.id == old.result_id)).mappings().one()
                return repo.credential_view(row)
            head = repo.head(conn, t.connection_heads, t.connection_heads.c.connection_id, connection_id, lock=True)
            if not head or head["version"] != data.expected_version:
                raise CatalogError(409 if head else 404, "revision_conflict" if head else "not_found")
            current = repo.active_credential(conn, connection_id, lock=True)
            version = (current["version"] if current else conn.execute(sa.select(sa.func.coalesce(sa.func.max(
                t.credential_bindings.c.version), 0)).where(t.credential_bindings.c.connection_id == connection_id)).scalar_one()) + 1
            now, binding_id = self.auth.now(), uuid4()
            if current:
                conn.execute(sa.update(t.credential_bindings).where(t.credential_bindings.c.id == current["id"]).values(revoked_at=now))
            conn.execute(sa.insert(t.credential_bindings).values(id=binding_id, connection_id=connection_id,
                version=version, source_type=data.source_type, secret_ref=data.secret_ref,
                environment=data.environment, account_ref=data.account_ref, project_ref=data.project_ref,
                created_at=now))
            next_head = head["version"] + 1
            conn.execute(sa.update(t.connection_heads).where(t.connection_heads.c.connection_id == connection_id)
                         .values(version=next_head))
            repo.record(conn, owner, "credential.bind", connection_id, data.operation_id, fp,
                next_head, binding_id, data.reason, now)
            row = conn.execute(sa.select(t.credential_bindings).where(t.credential_bindings.c.id == binding_id)).mappings().one()
            return repo.credential_view(row)

    def revoke_credential(self, raw, csrf, connection_id, data: RevokeCredential, peer="catalog"):
        data = RevokeCredential.model_validate(data)
        owner, encoded = self._password_proof(raw, csrf, data.current_password, peer,
            {"connections.write", "secrets.bind"})
        safe = data.model_dump(mode="json", exclude={"current_password"})
        fp = repo.fingerprint("credential.revoke", owner, connection_id, safe)
        with self.auth.engine.begin() as conn:
            actor, _, _ = staff_session(self.auth, conn, raw, {"connections.write", "secrets.bind"}, csrf=csrf, mutation=True)
            if actor["id"] != owner or not hmac.compare_digest(actor["password_hash"], encoded):
                raise AuthError(403, "reauth_required")
            old = repo.replay(conn, data.operation_id, fp)
            if old:
                return old
            head = repo.head(conn, t.connection_heads, t.connection_heads.c.connection_id, connection_id, lock=True)
            if not head or head["version"] != data.expected_version:
                raise CatalogError(409 if head else 404, "revision_conflict" if head else "not_found")
            current = repo.active_credential(conn, connection_id, lock=True)
            if not current:
                raise CatalogError(409, "credential_unavailable")
            now = self.auth.now()
            conn.execute(sa.update(t.credential_bindings).where(t.credential_bindings.c.id == current["id"])
                         .values(revoked_at=now))
            next_head = head["version"] + 1
            conn.execute(sa.update(t.connection_heads).where(t.connection_heads.c.connection_id == connection_id)
                         .values(version=next_head))
            return repo.record(conn, owner, "credential.revoke", connection_id, data.operation_id, fp,
                next_head, current["id"], data.reason, now)

    def proof(self, raw, csrf, capability_id, data: ProofInput):
        data = ProofInput.model_validate(data)
        with self.auth.engine.begin() as conn:
            actor, _, _ = staff_session(self.auth, conn, raw,
                {"catalog.write", "connections.write", "pricing.write"}, csrf=csrf, mutation=True)
            payload = data.model_dump(mode="json")
            fp = repo.fingerprint("contract.proof", actor["id"], capability_id, payload)
            old = repo.replay(conn, data.operation_id, fp)
            if old:
                row = conn.execute(sa.select(t.proofs).where(t.proofs.c.id == old.result_id)).mappings().one()
                return ProofView(proof_id=row["id"], **{k: row[k] for k in ("capability_id","connection_id","capability_hash","connection_hash","credential_version","evidence_hash","created_at")})
            cap_head = repo.head(conn, t.capability_heads, t.capability_heads.c.capability_id, capability_id, lock=True)
            conn_head = repo.head(conn, t.connection_heads, t.connection_heads.c.connection_id, data.connection_id, lock=True)
            if not cap_head or not conn_head:
                raise CatalogError(404, "not_found")
            if cap_head["version"] != data.expected_version or conn_head["version"] != data.connection_version:
                raise CatalogError(409, "revision_conflict")
            cap = repo.revision(conn, t.capability_revisions, cap_head["draft_revision_id"])
            connection_revision = repo.revision(conn, t.connection_revisions, conn_head["draft_revision_id"] or conn_head["published_revision_id"])
            cred = repo.active_credential(conn, data.connection_id, lock=True)
            if not cap or not connection_revision or not cred:
                raise CatalogError(409, "proof_prerequisite_missing")
            cap_content = CapabilityContent.model_validate_json(cap["content_json"])
            conn_content = ConnectionContent.model_validate_json(connection_revision["content_json"])
            fields = []
            if cap_content.connection_id != data.connection_id or cap_content.adapter_id != ADAPTER:
                fields.append("capability.connection")
            if not cap_content.resolutions:
                fields.append("capability.resolutions")
            if cap_content.price_credits <= 0:
                fields.append("pricing.rule")
            if conn_content.endpoint != ENDPOINT or conn_content.provider_id != PROVIDER:
                fields.append("connection.endpoint")
            if conn_content.max_concurrency <= 0:
                fields.append("connection.max_concurrency")
            if conn_content.rate_limit <= 0:
                fields.append("provider_account.rate_limit")
            if conn_content.environment != cred["environment"] or conn_content.account_ref != cred["account_ref"] or conn_content.project_ref != cred["project_ref"]:
                fields.append("credential.scope")
            if fields:
                raise CatalogError(422, "contract_proof_failed", tuple(fields))
            evidence = repo.digest(repo.canonical({"adapter": ADAPTER, "adapter_version": 1,
                "endpoint": ENDPOINT, "capability_hash": cap["content_hash"],
                "connection_hash": connection_revision["content_hash"], "credential_version": cred["version"],
                "network_called": False, "live_ready": False}))
            proof_id = uuid4()
            conn.execute(sa.insert(t.proofs).values(id=proof_id, capability_id=capability_id,
                connection_id=data.connection_id, capability_hash=cap["content_hash"],
                connection_hash=connection_revision["content_hash"], credential_version=cred["version"],
                evidence_hash=evidence, created_at=self.auth.now()))
            repo.record(conn, actor["id"], "contract.proof", capability_id, data.operation_id, fp,
                cap_head["version"], proof_id, data.reason, self.auth.now())
            return ProofView(proof_id=proof_id, capability_id=capability_id, connection_id=data.connection_id,
                capability_hash=cap["content_hash"], connection_hash=connection_revision["content_hash"],
                credential_version=cred["version"], evidence_hash=evidence, created_at=self.auth.now())

    def _proof_row(self, conn, proof_id):
        row = conn.execute(sa.select(t.proofs).where(t.proofs.c.id == proof_id)).mappings().first()
        if not row:
            raise CatalogError(404, "proof_not_found")
        return row

    def publish_connection(self, raw, csrf, connection_id, data: PublishInput):
        data = PublishInput.model_validate(data)
        with self.auth.engine.begin() as conn:
            actor, _, _ = staff_session(self.auth, conn, raw, {"connections.write"}, csrf=csrf, mutation=True)
            fp = repo.fingerprint("connection.publish", actor["id"], connection_id, data.model_dump(mode="json"))
            old = repo.replay(conn, data.operation_id, fp)
            if old: return old
            head = repo.head(conn, t.connection_heads, t.connection_heads.c.connection_id, connection_id, lock=True)
            if not head or head["version"] != data.expected_version:
                raise CatalogError(409 if head else 404, "revision_conflict" if head else "not_found")
            draft = repo.revision(conn, t.connection_revisions, head["draft_revision_id"])
            proof = self._proof_row(conn, data.proof_id)
            cred = repo.active_credential(conn, connection_id)
            if not draft or not cred or proof["connection_id"] != connection_id or proof["connection_hash"] != draft["content_hash"] or proof["credential_version"] != cred["version"]:
                raise CatalogError(409, "proof_stale")
            version = head["version"] + 1
            conn.execute(sa.update(t.connection_heads).where(t.connection_heads.c.connection_id == connection_id)
                .values(version=version, published_revision_id=draft["id"], draft_revision_id=None, runtime_state="disabled"))
            return repo.record(conn, actor["id"], "connection.publish", connection_id, data.operation_id, fp,
                version, draft["id"], data.reason, self.auth.now())

    def publish_capability(self, raw, csrf, capability_id, data: PublishInput):
        data = PublishInput.model_validate(data)
        with self.auth.engine.begin() as conn:
            actor, _, _ = staff_session(self.auth, conn, raw, {"catalog.write", "pricing.write"}, csrf=csrf, mutation=True)
            fp = repo.fingerprint("capability.publish", actor["id"], capability_id, data.model_dump(mode="json"))
            old = repo.replay(conn, data.operation_id, fp)
            if old: return old
            head = repo.head(conn, t.capability_heads, t.capability_heads.c.capability_id, capability_id, lock=True)
            if not head or head["version"] != data.expected_version:
                raise CatalogError(409 if head else 404, "revision_conflict" if head else "not_found")
            draft = repo.revision(conn, t.capability_revisions, head["draft_revision_id"])
            proof = self._proof_row(conn, data.proof_id)
            if not draft or proof["capability_id"] != capability_id or proof["capability_hash"] != draft["content_hash"]:
                raise CatalogError(409, "proof_stale")
            conn_head = repo.head(conn, t.connection_heads, t.connection_heads.c.connection_id, proof["connection_id"])
            published_conn = repo.revision(conn, t.connection_revisions, conn_head["published_revision_id"] if conn_head else None)
            cred = repo.active_credential(conn, proof["connection_id"])
            if not conn_head or not published_conn or not cred or published_conn["content_hash"] != proof["connection_hash"] or cred["version"] != proof["credential_version"]:
                raise CatalogError(409, "proof_stale")
            version = head["version"] + 1
            conn.execute(sa.update(t.capability_heads).where(t.capability_heads.c.capability_id == capability_id)
                .values(version=version, published_revision_id=draft["id"], draft_revision_id=None))
            return repo.record(conn, actor["id"], "capability.publish", capability_id, data.operation_id, fp,
                version, draft["id"], data.reason, self.auth.now())

    def disable_capability(self, raw, csrf, capability_id, data: DisableInput):
        data = DisableInput.model_validate(data)
        with self.auth.engine.begin() as conn:
            actor, _, _ = staff_session(self.auth, conn, raw, {"catalog.write"}, csrf=csrf, mutation=True)
            fp = repo.fingerprint("capability.disable", actor["id"], capability_id, data.model_dump(mode="json"))
            old = repo.replay(conn, data.operation_id, fp)
            if old: return old
            head = repo.head(conn, t.capability_heads, t.capability_heads.c.capability_id, capability_id, lock=True)
            if not head or head["version"] != data.expected_version:
                raise CatalogError(409 if head else 404, "revision_conflict" if head else "not_found")
            version = head["version"] + 1
            conn.execute(sa.update(t.capability_heads).where(t.capability_heads.c.capability_id == capability_id)
                .values(version=version, published_revision_id=None))
            return repo.record(conn, actor["id"], "capability.disable", capability_id, data.operation_id, fp,
                version, None, data.reason, self.auth.now())
