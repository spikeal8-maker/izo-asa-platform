"""Versioned, permission-checked catalog without provider calls or ledger writes."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.accounts import repository as ar, tables as a
from izo.accounts.security import AuthError
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.catalog.schemas import CatalogPatch
from izo.catalog.service import CatalogError, CatalogService
from izo.catalog import tables as c
from izo.access import tables as access_tables
from izo.access.permissions import GLOBAL_DELEGABLE
from izo.access.service import AccessService
from izo.admin import tables as admin_tables
from izo.chat import tables as chat
from izo.chat.schemas import MODEL_REVISION, RequestCreate
from izo.chat.service import ChatError
from test_admin import admin_env, password_hash
from test_chat import chat_env, connect_key


@pytest.fixture
def catalog_env(tmp_path):
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "catalog.sqlite"),
                              connect_args={"check_same_thread": False})
    @sa.event.listens_for(engine, "connect")
    def configure(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
    a.metadata.create_all(engine)
    auth = AuthService(engine, AuthSettings(registration="invite", rate_secret="x" * 40),
                       clock=lambda: 2000)
    sessions = []
    with engine.begin() as conn:
        for name, grants in (("owner", ("catalog.read", "catalog.write", "pricing.write")),
                             ("editor", ("catalog.read", "catalog.write")),
                             ("reader", ("catalog.read",)), ("user", ())):
            uid, iid = uuid4(), uuid4()
            conn.execute(sa.insert(a.accounts).values(
                id=uid, public_code=uid.hex[:16], display_name=name,
                state="active", created_at=1000))
            conn.execute(sa.insert(a.identities).values(
                id=iid, account_id=uid, provider="email",
                subject=uid.hex + "@example.invalid", verified_at=1000))
            for permission in grants:
                conn.execute(sa.insert(a.permissions).values(account_id=uid, permission=permission))
            sessions.append(auth._new_session(conn, ar.account_by_id(conn, uid), "fixture", 2000))
    yield CatalogService(auth), sessions, engine
    engine.dispose()


def patch(revision=1, **changes):
    values = dict(operation_id=uuid4(), expected_revision=revision, published=True,
                  enabled=True, is_default=False, reason="catalog acceptance",
                  price=dict(currency="RUB", input_kopeks_per_million=None,
                             output_kopeks_per_million=None, image_kopeks_per_image=None))
    values.update(changes)
    return CatalogPatch(**values)


def update(env, who, model="deepseek-v4-pro", command=None):
    service, sessions, _ = env
    return service.patch(sessions[who].bearer, sessions[who].view.csrf_token,
                         model, command or patch())


def test_catalog_read_is_staff_owned_and_unknown_price_is_null(catalog_env):
    service, sessions, _ = catalog_env
    view = service.read(sessions[2].bearer)
    assert view.revision == 1
    assert {item.id for item in view.models} == {
        "deepseek-flash", "deepseek-v4-pro", "fal.flux2.klein.4b"}
    assert all(item.price.currency == "RUB" for item in view.models)
    assert all(item.price.input_kopeks_per_million is None for item in view.models)
    assert all(item.price_source == "unset" for item in view.models)
    assert "catalog.read" in view.permissions
    with pytest.raises(AuthError, match="forbidden"):
        service.read(sessions[3].bearer)


def test_separate_catalog_and_pricing_permissions(catalog_env):
    _, sessions, engine = catalog_env
    with pytest.raises(AuthError, match="forbidden"):
        update(catalog_env, 2, command=patch(enabled=False))
    changed = update(catalog_env, 1, command=patch(is_default=True))
    assert changed.revision == 2
    price = dict(currency="RUB", input_kopeks_per_million=123,
                 output_kopeks_per_million=456, image_kopeks_per_image=None)
    with pytest.raises(AuthError, match="forbidden"):
        update(catalog_env, 1, command=patch(revision=2, price=price))
    view = update(catalog_env, 0, command=patch(revision=2, is_default=True, price=price))
    assert view.revision == 3
    assert next(m for m in view.models if m.id == "deepseek-v4-pro").price.input_kopeks_per_million == 123
    assert next(m for m in view.models if m.id == "deepseek-v4-pro").price_source == "admin_manual"
    with engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(admin_tables.events).where(
            admin_tables.events.c.action == "catalog.update",
            admin_tables.events.c.outcome == "denied")).scalar_one() == 2


def test_cas_replay_audit_and_unapproved_model(catalog_env):
    service, sessions, engine = catalog_env
    command = patch(is_default=True)
    result = update(catalog_env, 0, command=command)
    assert update(catalog_env, 0, command=command).revision == result.revision
    with pytest.raises(CatalogError, match="catalog_operation_conflict"):
        update(catalog_env, 0, command=command.model_copy(update={"reason": "different reason"}))
    with pytest.raises(CatalogError, match="catalog_revision_conflict"):
        update(catalog_env, 0, command=patch(revision=1))
    with pytest.raises(CatalogError, match="model_not_allowed"):
        update(catalog_env, 0, model="openrouter/unknown", command=patch(revision=2))
    later = update(catalog_env, 0, model="deepseek-flash",
                   command=patch(revision=2, is_default=False))
    assert later.revision == 3
    assert update(catalog_env, 0, command=command).revision == 3
    with engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(c.events)).scalar_one() == 2
        assert conn.execute(sa.select(c.state.c.revision)).scalar_one() == 3


def test_image_metadata_cannot_claim_job_runtime_control(catalog_env):
    with pytest.raises(CatalogError, match="image_runtime_not_bound"):
        update(catalog_env, 0, model="fal.flux2.klein.4b", command=patch())
    image_price = dict(currency="RUB", input_kopeks_per_million=None,
                       output_kopeks_per_million=None, image_kopeks_per_image=12000)
    view = update(catalog_env, 0, model="fal.flux2.klein.4b",
                  command=patch(published=False, enabled=False, price=image_price))
    assert next(m for m in view.models if m.modality == "image").price.image_kopeks_per_image == 12000


def test_existing_local_owner_explicit_pricing_upgrade(admin_env, monkeypatch):
    admin, users, _ = admin_env
    service = AccessService(admin.auth)
    service.enroll_local_owner(users[0],
        tuple(item for item in GLOBAL_DELEGABLE if item != "pricing.write"))
    with pytest.raises(AuthError, match="local_upgrade_disabled"):
        service.upgrade_local_owner_permission(users[0], "pricing.write")
    monkeypatch.setenv("IZO_ACCESS_BOOTSTRAP", "isolated")
    with pytest.raises(AuthError, match="access_owner_required"):
        service.upgrade_local_owner_permission(users[1], "pricing.write")
    assert service.upgrade_local_owner_permission(users[0], "pricing.write") is True
    assert service.upgrade_local_owner_permission(users[0], "pricing.write") is False
    with service.auth.engine.begin() as conn:
        for table in (a.permissions, access_tables.grants, access_tables.ceilings):
            row = conn.execute(sa.select(table).where(
                table.c.account_id == users[0], table.c.permission == "pricing.write")).mappings().one()
            assert row["expires_at"] is None
        assert conn.execute(sa.select(access_tables.state.c.version)).scalar_one() == 2
        assert conn.execute(sa.select(sa.func.count()).select_from(admin_tables.events).where(
            admin_tables.events.c.action == "access.local_owner_upgrade")).scalar_one() == 1


def test_local_owner_upgrade_rejects_partial_permission(admin_env, monkeypatch):
    admin, users, _ = admin_env
    service = AccessService(admin.auth)
    service.enroll_local_owner(users[0],
        tuple(item for item in GLOBAL_DELEGABLE if item != "pricing.write"))
    monkeypatch.setenv("IZO_ACCESS_BOOTSTRAP", "isolated")
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(a.permissions).values(
            account_id=users[0], permission="pricing.write"))
    with pytest.raises(AuthError, match="permission_provenance_conflict"):
        service.upgrade_local_owner_permission(users[0], "pricing.write")
    with pytest.raises(ValueError):
        service.upgrade_local_owner_permission(users[0], "secrets.bind")


def test_price_null_zero_and_disabled_model_admission(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    policy = service.public_policy(alice.bearer)
    assert policy.default_model == "deepseek-flash"
    assert [m.id for m in policy.models] == ["deepseek-flash", "deepseek-v4-pro"]
    assert policy.models[0].price.input_kopeks_per_million is None
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    command = RequestCreate(request_id=uuid4(), text="hello", model="deepseek-v4-pro")
    accepted = service.create_request(alice.bearer, alice.view.csrf_token, thread.id, command)
    with service.engine.begin() as conn:
        conn.execute(sa.update(c.state).where(c.state.c.id == 1).values(revision=2))
        conn.execute(sa.update(c.models).where(c.models.c.id == "deepseek-v4-pro")
                     .values(enabled=False))
        conn.execute(sa.update(c.models).where(c.models.c.id == "deepseek-flash")
                     .values(input_kopeks_per_million=0, output_kopeks_per_million=199))
    refreshed = service.public_policy(alice.bearer)
    assert [m.id for m in refreshed.models] == ["deepseek-flash"]
    assert refreshed.models[0].price.input_kopeks_per_million == 0
    assert refreshed.models[0].price.output_kopeks_per_million == 199
    with pytest.raises(ChatError, match="model_not_allowed"):
        service.create_request(alice.bearer, alice.view.csrf_token, thread.id,
            RequestCreate(request_id=uuid4(), text="new", model="deepseek-v4-pro"))
    assert service.create_request(alice.bearer, alice.view.csrf_token,
                                  thread.id, command) == accepted
    with service.engine.begin() as conn:
        revision = conn.execute(sa.select(chat.requests.c.model_revision).where(
            chat.requests.c.id == accepted.id)).scalar_one()
        assert "catalog-1" in revision


def test_legacy_fingerprint_replay_uses_stored_model_revision(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    command = RequestCreate(request_id=uuid4(), text="legacy", model="deepseek-v4-pro")
    accepted = service.create_request(alice.bearer, alice.view.csrf_token, thread.id, command)
    with service.engine.begin() as conn:
        row = conn.execute(sa.select(chat.requests).where(chat.requests.c.id == accepted.id)).mappings().one()
        old_hash = service._request_fingerprint(thread.id, command.text, command.model,
            row["connection_id"], row["credential_generation"], MODEL_REVISION)
        conn.execute(sa.update(chat.requests).where(chat.requests.c.id == accepted.id).values(
            model_revision=MODEL_REVISION, fingerprint=old_hash))
        conn.execute(sa.update(c.models).where(c.models.c.id == command.model)
                     .values(enabled=False))
    assert service.create_request(alice.bearer, alice.view.csrf_token, thread.id, command) == accepted
