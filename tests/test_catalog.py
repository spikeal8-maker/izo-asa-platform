"""CATALOG-001 typed lifecycle on SQLite; PostgreSQL race/persistence is separate acceptance."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.accounts import tables as accounts
from izo.accounts.security import AuthError
from izo.catalog import tables as t
from izo.catalog.schemas import (CapabilityDraft, ConnectionDraft, CredentialBind, DisableInput,
    ProofInput, PublishInput, CatalogError)
from izo.catalog.service import CatalogService
from izo.catalog.runtime import resolve_execution
from izo.jobs.catalog import JobSettings
from izo.jobs.schemas import QuoteInput, JobError
from izo.jobs.service import JobService
from test_admin import admin_env, password_hash, PASSWORD

PERMISSIONS = ("catalog.read", "catalog.write", "connections.read", "connections.write",
               "secrets.bind", "pricing.write")


@pytest.fixture
def catalog_env(admin_env):
    admin, users, sessions = admin_env
    with admin.auth.engine.begin() as conn:
        conn.execute(sa.insert(accounts.permissions), [
            {"account_id": users[0], "permission": permission} for permission in PERMISSIONS
        ])
    return CatalogService(admin.auth), users, sessions


def connection(expected=0, **changes):
    values = dict(operation_id=uuid4(), expected_version=expected, reason="catalog fixture",
        account_ref="openrouter-test-account", project_ref="image-project", environment="test",
        max_concurrency=2, rate_limit=20, rate_window_seconds=60, spend_cap_minor=0,
        currency="USD", timeout_seconds=180, allow_fallbacks=False)
    values.update(changes)
    return ConnectionDraft(**values)


def credential(expected, **changes):
    values = dict(operation_id=uuid4(), expected_version=expected, reason="catalog credential fixture",
        source_type="env", secret_ref="IZO_OPENROUTER_API_KEY", environment="test",
        account_ref="openrouter-test-account", project_ref="image-project", current_password=PASSWORD)
    values.update(changes)
    return CredentialBind(**values)


def capability(expected=0, **changes):
    values = dict(operation_id=uuid4(), expected_version=expected, reason="catalog model fixture",
        name="OpenRouter image test", help="Non-live catalog fixture", adapter_id="openrouter.images.v1",
        model_id="google/gemini-2.5-flash-image", connection_id="openrouter-primary",
        resolutions=("512",), price_credits=3)
    values.update(changes)
    return CapabilityDraft(**values)


def prepare(service, session, *, cred_changes=None, cap_changes=None, conn_changes=None):
    csrf = session.view.csrf_token
    service.save_connection(session.bearer, csrf, "openrouter-primary", connection(**(conn_changes or {})))
    service.bind_credential(session.bearer, csrf, "openrouter-primary",
        credential(1, **(cred_changes or {})), "fixture")
    service.save_capability(session.bearer, csrf, "openrouter.image.v1", capability(**(cap_changes or {})))
    return service.proof(session.bearer, csrf, "openrouter.image.v1",
        ProofInput(operation_id=uuid4(), expected_version=1, connection_id="openrouter-primary",
                   connection_version=2, reason="offline contract proof"))


def publish_all(service, session):
    proof = prepare(service, session)
    csrf = session.view.csrf_token
    service.publish_connection(session.bearer, csrf, "openrouter-primary",
        PublishInput(operation_id=uuid4(), expected_version=2, proof_id=proof.proof_id,
                     reason="publish disabled connection"))
    service.publish_capability(session.bearer, csrf, "openrouter.image.v1",
        PublishInput(operation_id=uuid4(), expected_version=1, proof_id=proof.proof_id,
                     reason="publish capability metadata"))
    return proof


def test_new_catalog_is_not_public_or_live(catalog_env):
    service, _, sessions = catalog_env
    with pytest.raises(AuthError, match="forbidden"):
        service.capabilities(sessions[1].bearer)
    assert service.capabilities(sessions[0].bearer).items == ()
    assert service.connections(sessions[0].bearer).items == ()
    provider = service.providers(sessions[0].bearer).items[0]
    assert provider.provider_id == "openrouter" and not provider.live_enabled


def test_arbitrary_endpoint_and_raw_secret_are_not_schema_fields():
    with pytest.raises(ValidationError):
        ConnectionDraft.model_validate(connection().model_dump() | {"endpoint":"https://evil.invalid"})
    with pytest.raises(ValidationError):
        CredentialBind.model_validate(credential(1).model_dump() | {"api_key":"raw-secret"})
    with pytest.raises(ValidationError):
        credential(1, secret_ref="OTHER_ENV_KEY")
    with pytest.raises(ValidationError):
        credential(1, secret_ref="../../etc/passwd", source_type="secret_file")
    with pytest.raises(ValidationError):
        credential(1, secret_ref="/etc/passwd", source_type="secret_file")
    with pytest.raises(ValidationError):
        credential(1, secret_ref="sk-or-v1-not-a-reference", source_type="secret_manager")
    # Logical aliases are accepted; values are resolved only by a later
    # worker-side resolver, never by this catalog service.
    assert credential(1, source_type="secret_file", secret_ref="openrouter/test-primary").secret_ref == "openrouter/test-primary"
    assert credential(1, source_type="secret_manager", secret_ref="vault/izo/openrouter/v2").secret_ref.endswith("/v2")


def test_draft_and_credential_metadata_are_fail_closed(catalog_env):
    service, _, sessions = catalog_env; s = sessions[0]; csrf = s.view.csrf_token
    receipt = service.save_connection(s.bearer, csrf, "openrouter-primary", connection())
    assert receipt.result_version == 1
    view = service.connection(s.bearer, "openrouter-primary")
    assert view.runtime_state == "disabled" and view.published is None and view.draft
    binding = service.bind_credential(s.bearer, csrf, "openrouter-primary", credential(1), "fixture")
    assert binding.version == 1 and binding.state == "active"
    assert len(binding.reference_fingerprint) == 64
    assert "IZO_OPENROUTER_API_KEY" not in binding.model_dump_json()
    assert service.connection(s.bearer, "openrouter-primary").version == 2


def test_wrong_password_does_not_create_binding(catalog_env):
    service, _, sessions = catalog_env; s=sessions[0]
    service.save_connection(s.bearer, s.view.csrf_token, "openrouter-primary", connection())
    with pytest.raises(AuthError, match="reauth_required"):
        service.bind_credential(s.bearer, s.view.csrf_token, "openrouter-primary",
            credential(1, current_password="wrong password value"), "fixture")
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.credential_bindings)).scalar_one() == 0


def test_contract_proof_is_offline_and_publish_stays_disabled(catalog_env):
    service, _, sessions = catalog_env; s=sessions[0]
    proof = publish_all(service, s)
    assert proof.proof_kind == "contract" and not proof.network_called and not proof.live_ready
    model = service.capability(s.bearer, "openrouter.image.v1")
    conn = service.connection(s.bearer, "openrouter-primary")
    assert model.published and model.draft is None and not model.runtime_available
    assert conn.published and conn.draft is None and conn.runtime_state == "disabled"
    assert conn.content.endpoint == "https://openrouter.ai/api/v1/images"


@pytest.mark.parametrize("changes,field", [
    ({"price_credits":0}, "pricing.rule"),
    ({"resolutions":()}, "capability.resolutions"),
])
def test_proof_rejects_incomplete_capability(catalog_env, changes, field):
    service, _, sessions = catalog_env; s=sessions[0]
    with pytest.raises(CatalogError, match="contract_proof_failed") as failure:
        prepare(service, s, cap_changes=changes)
    assert field in failure.value.fields


def test_proof_rejects_credential_scope_mismatch(catalog_env):
    service, _, sessions = catalog_env; s=sessions[0]
    with pytest.raises(CatalogError, match="contract_proof_failed") as failure:
        prepare(service, s, cred_changes={"account_ref":"different-account"})
    assert "credential.scope" in failure.value.fields


def test_expected_version_and_operation_id_prevent_lost_update(catalog_env):
    service, _, sessions = catalog_env; s=sessions[0]; csrf=s.view.csrf_token
    cmd = connection()
    first = service.save_connection(s.bearer, csrf, "openrouter-primary", cmd)
    assert service.save_connection(s.bearer, csrf, "openrouter-primary", cmd) == first
    with pytest.raises(CatalogError, match="idempotency_conflict"):
        service.save_connection(s.bearer, csrf, "openrouter-primary",
            ConnectionDraft.model_validate(cmd.model_dump() | {"max_concurrency":3}))
    with pytest.raises(CatalogError, match="revision_conflict"):
        service.save_connection(s.bearer, csrf, "openrouter-primary", connection(expected=0, max_concurrency=4))


def test_rotation_revokes_old_binding_and_stales_old_proof(catalog_env):
    service, _, sessions = catalog_env; s=sessions[0]; csrf=s.view.csrf_token
    proof = prepare(service, s)
    service.publish_connection(s.bearer, csrf, "openrouter-primary",
        PublishInput(operation_id=uuid4(), expected_version=2, proof_id=proof.proof_id,
                     reason="publish connection"))
    rotated = service.bind_credential(s.bearer, csrf, "openrouter-primary",
        credential(3, source_type="secret_manager", secret_ref="vault/izo/openrouter/v2"), "fixture")
    assert rotated.version == 2
    with pytest.raises(CatalogError, match="proof_stale"):
        service.publish_capability(s.bearer, csrf, "openrouter.image.v1",
            PublishInput(operation_id=uuid4(), expected_version=1, proof_id=proof.proof_id,
                         reason="old proof must not publish"))
    with service.auth.engine.connect() as conn:
        rows = conn.execute(sa.select(t.credential_bindings).order_by(t.credential_bindings.c.version)).mappings().all()
        assert rows[0]["revoked_at"] is not None and rows[1]["revoked_at"] is None


def test_disable_removes_public_pointer_not_history(catalog_env):
    service, _, sessions = catalog_env; s=sessions[0]; csrf=s.view.csrf_token
    publish_all(service, s)
    receipt = service.disable_capability(s.bearer, csrf, "openrouter.image.v1",
        DisableInput(operation_id=uuid4(), expected_version=2, reason="disable new submissions"))
    assert receipt.result_version == 3
    assert service.capability(s.bearer, "openrouter.image.v1").published is None
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.capability_revisions)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(t.proofs)).scalar_one() == 1


def test_published_catalog_and_shared_env_cannot_activate_external_admission(catalog_env, monkeypatch):
    service, _, sessions = catalog_env; s = sessions[0]
    publish_all(service, s)
    # Even a complete legacy/shared environment configuration is not an
    # admission authority once the catalog exists. CATALOG-001 has no live
    # activation state, so HTTP-style JobService must fail closed.
    monkeypatch.setenv("IZO_OPENROUTER_ENABLED", "true")
    monkeypatch.setenv("IZO_OPENROUTER_MODEL", "google/gemini-2.5-flash-image")
    monkeypatch.setenv("IZO_OPENROUTER_PRICE_CREDITS", "3")
    monkeypatch.setenv("IZO_OPENROUTER_RESOLUTIONS", '["512"]')
    jobs = JobService(service.auth, JobSettings(enabled=True))
    assert jobs.openrouter is None
    draft = QuoteInput(capability_id="openrouter.image.v1", prompt="must remain disabled",
                       width=512, height=512)
    with pytest.raises(JobError, match="provider_unavailable") as failure:
        jobs.quote(s.bearer, s.view.csrf_token, draft)
    assert failure.value.status == 503
    with service.auth.engine.begin() as conn:
        with pytest.raises(CatalogError, match="provider_unavailable"):
            resolve_execution(conn, "openrouter.image.v1", 512, 512)
