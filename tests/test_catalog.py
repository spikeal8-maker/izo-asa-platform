"""CATALOG-002 lifecycle on SQLite; PostgreSQL race/persistence is separate acceptance."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.access.schemas import GrantAccessInput
from izo.access.service import AccessService
from izo.accounts.security import AuthError
from izo.catalog import tables as t
from izo.catalog.schemas import (CapabilityDraft, ConnectionDraft, CredentialBind, DisableInput,
    ProofInput, PublishInput, CatalogError)
from izo.catalog.service import CatalogService
from izo.jobs import catalog as job_catalog
from test_admin import admin_env, password_hash, PASSWORD

PERMISSIONS = ("catalog.read", "catalog.write", "connections.read", "connections.write", "secrets.bind")
CONNECTION = "fal-klein-4b-v1"
CAPABILITY = "fal.flux2.klein.4b"


@pytest.fixture
def catalog_env(admin_env):
    admin, users, sessions = admin_env
    access = AccessService(admin.auth)
    access.enroll_local_owner(users[0])
    for permission in PERMISSIONS:
        access.grant(sessions[0].bearer, sessions[0].view.csrf_token, users[2],
            GrantAccessInput(operation_id=uuid4(), permission=permission, scope="global",
                ttl_seconds=3600, case_reference="CATALOG-"+uuid4().hex,
                current_password=PASSWORD), "fixture")
    return CatalogService(admin.auth), access, users, sessions


def connection(expected=0, **changes):
    values = dict(operation_id=uuid4(), expected_version=expected, reason="catalog fixture",
        provider_id="fal", account_ref="fal-test-account", project_ref="image-project",
        environment="test", max_concurrency=2, rate_limit=20, rate_window_seconds=60,
        timeout_seconds=180)
    values.update(changes)
    return ConnectionDraft(**values)


def credential(expected, **changes):
    values = dict(operation_id=uuid4(), expected_version=expected,
        reason="catalog credential fixture", source_type="env", secret_ref="IZO_FAL_KEY",
        environment="test", account_ref="fal-test-account", project_ref="image-project",
        current_password=PASSWORD)
    values.update(changes)
    return CredentialBind(**values)


def capability(expected=0, **changes):
    values = dict(operation_id=uuid4(), expected_version=expected, reason="catalog model fixture",
        name="FLUX.2 Klein 4B", help="Non-live catalog fixture", adapter_id="fal.images.v1",
        model_id="fal-ai/flux-2/klein/4b", connection_id=CONNECTION)
    values.update(changes)
    return CapabilityDraft(**values)


def prepare(service, session):
    csrf = session.view.csrf_token
    service.save_connection(session.bearer, csrf, CONNECTION, connection())
    service.bind_credential(session.bearer, csrf, CONNECTION, credential(1), "fixture")
    service.save_capability(session.bearer, csrf, CAPABILITY, capability())
    return service.proof(session.bearer, csrf, CAPABILITY,
        ProofInput(operation_id=uuid4(), expected_version=1, connection_id=CONNECTION,
                   connection_version=2, reason="offline contract proof"))


def publish_all(service, session):
    proof = prepare(service, session)
    csrf = session.view.csrf_token
    service.publish_connection(session.bearer, csrf, CONNECTION,
        PublishInput(operation_id=uuid4(), expected_version=2, proof_id=proof.proof_id,
                     reason="publish disabled connection"))
    service.publish_capability(session.bearer, csrf, CAPABILITY,
        PublishInput(operation_id=uuid4(), expected_version=1, proof_id=proof.proof_id,
                     reason="publish capability metadata"))
    return proof


def test_access_provisioning_materializes_catalog_permissions(catalog_env):
    _, access, users, sessions = catalog_env
    card = access.subject(sessions[0].bearer, users[2])
    managed = {item.permission for item in card.permissions if item.managed}
    assert set(PERMISSIONS) <= managed


def test_new_catalog_is_staff_only_and_not_live(catalog_env):
    service, _, _, sessions = catalog_env
    with pytest.raises(AuthError, match="forbidden"):
        service.capabilities(sessions[1].bearer)
    assert service.capabilities(sessions[2].bearer).items == ()
    provider = service.providers(sessions[2].bearer).items[0]
    assert provider.provider_id == "fal" and provider.endpoint == "https://queue.fal.run"
    assert provider.adapters == ("fal.images.v1",) and not provider.live_enabled


def test_unknown_provider_adapter_endpoint_and_raw_secret_fail_closed(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]; csrf=s.view.csrf_token
    with pytest.raises(ValidationError):
        ConnectionDraft.model_validate(connection().model_dump() | {"endpoint":"https://evil.invalid"})
    with pytest.raises(ValidationError):
        ConnectionDraft.model_validate(connection().model_dump() | {"spend_cap_minor":5000})
    with pytest.raises(ValidationError):
        ConnectionDraft.model_validate(connection().model_dump() | {"allow_fallbacks":True})
    with pytest.raises(ValidationError):
        CapabilityDraft.model_validate(capability().model_dump() | {"price_credits":3})
    with pytest.raises(ValidationError):
        CapabilityDraft.model_validate(capability().model_dump() | {"resolutions":["512"]})
    with pytest.raises(ValidationError):
        CredentialBind.model_validate(credential(1).model_dump() | {"api_key":"raw-secret"})
    with pytest.raises(CatalogError, match="provider_unsupported"):
        service.save_connection(s.bearer, csrf, "bad-provider", connection(provider_id="unknown"))
    with pytest.raises(CatalogError, match="adapter_unsupported"):
        service.save_capability(s.bearer, csrf, "bad.adapter", capability(adapter_id="unknown.images.v1"))


def test_draft_and_credential_metadata_are_fail_closed(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]; csrf=s.view.csrf_token
    receipt = service.save_connection(s.bearer, csrf, CONNECTION, connection())
    assert receipt.result_version == 1
    view = service.connection(s.bearer, CONNECTION)
    assert view.runtime_state == "disabled" and view.published is None and view.draft
    binding = service.bind_credential(s.bearer, csrf, CONNECTION, credential(1), "fixture")
    assert binding.version == 1 and binding.state == "active" and len(binding.reference_fingerprint) == 64
    assert "IZO_FAL_KEY" not in binding.model_dump_json()
    assert service.connection(s.bearer, CONNECTION).version == 2


def test_secret_reference_and_scope_are_provider_owned(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]; csrf=s.view.csrf_token
    service.save_connection(s.bearer, csrf, CONNECTION, connection())
    with pytest.raises(CatalogError, match="secret_reference_unapproved"):
        service.bind_credential(s.bearer, csrf, CONNECTION, credential(1, secret_ref="OTHER_KEY"), "fixture")
    with pytest.raises(CatalogError, match="credential_scope_mismatch"):
        service.bind_credential(s.bearer, csrf, CONNECTION,
            credential(1, account_ref="different-account"), "fixture")
    assert credential(1, source_type="secret_file", secret_ref="fal/test-primary").secret_ref == "fal/test-primary"
    assert credential(1, source_type="secret_manager", secret_ref="vault/izo/fal/v2").secret_ref.endswith("/v2")


def test_wrong_password_does_not_create_binding(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]
    service.save_connection(s.bearer, s.view.csrf_token, CONNECTION, connection())
    with pytest.raises(AuthError, match="reauth_required"):
        service.bind_credential(s.bearer, s.view.csrf_token, CONNECTION,
            credential(1, current_password="wrong password value"), "fixture")
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.credential_bindings)).scalar_one() == 0


def test_contract_proof_is_offline_and_publish_stays_disabled(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]
    proof = publish_all(service, s)
    assert proof.proof_kind == "contract" and not proof.network_called and not proof.live_ready
    model = service.capability(s.bearer, CAPABILITY)
    conn = service.connection(s.bearer, CONNECTION)
    assert model.published and model.draft is None and not model.runtime_available
    assert conn.published and conn.draft is None and conn.runtime_state == "disabled"
    assert conn.content.provider_id == "fal" and conn.content.endpoint == "https://queue.fal.run"


def test_proof_rejects_nonready_connection_limits(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]; csrf=s.view.csrf_token
    service.save_connection(s.bearer, csrf, CONNECTION, connection(max_concurrency=0, rate_limit=0))
    service.bind_credential(s.bearer, csrf, CONNECTION, credential(1), "fixture")
    service.save_capability(s.bearer, csrf, CAPABILITY, capability())
    with pytest.raises(CatalogError, match="contract_proof_failed") as failure:
        service.proof(s.bearer, csrf, CAPABILITY,
            ProofInput(operation_id=uuid4(), expected_version=1, connection_id=CONNECTION,
                       connection_version=2, reason="reject incomplete contract"))
    assert {"connection.max_concurrency","provider_account.rate_limit"} <= set(failure.value.fields)


def test_expected_version_and_operation_id_prevent_lost_update(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]; csrf=s.view.csrf_token
    cmd = connection()
    first = service.save_connection(s.bearer, csrf, CONNECTION, cmd)
    assert service.save_connection(s.bearer, csrf, CONNECTION, cmd) == first
    with pytest.raises(CatalogError, match="idempotency_conflict"):
        service.save_connection(s.bearer, csrf, CONNECTION,
            ConnectionDraft.model_validate(cmd.model_dump() | {"max_concurrency":3}))
    with pytest.raises(CatalogError, match="revision_conflict"):
        service.save_connection(s.bearer, csrf, CONNECTION, connection(expected=0, max_concurrency=4))


def test_rotation_revokes_old_binding_and_stales_old_proof(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]; csrf=s.view.csrf_token
    proof = prepare(service, s)
    service.publish_connection(s.bearer, csrf, CONNECTION,
        PublishInput(operation_id=uuid4(), expected_version=2, proof_id=proof.proof_id,
                     reason="publish connection"))
    rotated = service.bind_credential(s.bearer, csrf, CONNECTION,
        credential(3, source_type="secret_manager", secret_ref="vault/izo/fal/v2"), "fixture")
    assert rotated.version == 2
    with pytest.raises(CatalogError, match="proof_stale"):
        service.publish_capability(s.bearer, csrf, CAPABILITY,
            PublishInput(operation_id=uuid4(), expected_version=1, proof_id=proof.proof_id,
                         reason="old proof must not publish"))


def test_disable_removes_published_pointer_not_history(catalog_env):
    service, _, _, sessions = catalog_env; s=sessions[2]; csrf=s.view.csrf_token
    publish_all(service, s)
    receipt = service.disable_capability(s.bearer, csrf, CAPABILITY,
        DisableInput(operation_id=uuid4(), expected_version=2, reason="disable new publication"))
    assert receipt.result_version == 3
    assert service.capability(s.bearer, CAPABILITY).published is None
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.capability_revisions)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(t.proofs)).scalar_one() == 1


def test_catalog_does_not_replace_current_jobs_runtime(catalog_env):
    service, _, _, sessions = catalog_env; publish_all(service, sessions[2])
    spec = job_catalog.capability(job_catalog.FAL_CAPABILITY)
    assert spec.id == CAPABILITY and spec.pool == job_catalog.FAL_POOL
    assert spec.version == "fal-klein4b-1" and spec.credits == 1
