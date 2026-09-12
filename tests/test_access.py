"""ACCESS-001 delegation on existing Accounts permission materialization."""
from uuid import uuid4
import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.accounts import tables as accounts
from izo.accounts.security import AuthError
from izo.access import tables as access_tables
from izo.access.permissions import GLOBAL_DELEGABLE, OWNER_EFFECTIVE
from izo.access.schemas import GrantAccessInput, RevokeAccessInput
from izo.access.service import AccessService
from izo.admin.service import AdminService
from test_admin import admin_env, password_hash, PASSWORD


@pytest.fixture
def access_env(admin_env):
    admin, users, sessions = admin_env
    service = AccessService(admin.auth)
    service.enroll_local_owner(users[0])
    return service, users, sessions


def grant_input(permission="plans.write", *, operation=None, ttl=3600, password=PASSWORD):
    return GrantAccessInput(operation_id=operation or uuid4(), permission=permission,
        scope="global", ttl_seconds=ttl, case_reference="ACCESS-"+uuid4().hex,
        current_password=password)


def revoke_input(permission="plans.write", *, operation=None, password=PASSWORD):
    return RevokeAccessInput(operation_id=operation or uuid4(), permission=permission,
        scope="global", case_reference="ACCESS-"+uuid4().hex, current_password=password)

def grant(env, target=2, data=None):
    service, users, sessions = env
    command = data or grant_input()
    return service.grant(sessions[0].bearer, sessions[0].view.csrf_token,
        users[target], command, "fixture")


def revoke(env, target=2, data=None):
    service, users, sessions = env
    command = data or revoke_input()
    return service.revoke(sessions[0].bearer, sessions[0].view.csrf_token,
        users[target], command, "fixture")


def test_local_owner_has_explicit_ceiling_and_materialized_permissions(access_env):
    service, users, sessions = access_env
    view = service.me(sessions[0].bearer)
    assert set(view.delegation_ceiling) == set(GLOBAL_DELEGABLE)
    assert {"access.read", "access.manage", "plans.write"} <= set(view.permissions)
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(access_tables.state.c.version)).scalar_one() == 1


def test_grant_materializes_permission_and_exact_retry(access_env):
    service, users, sessions = access_env
    operation = uuid4(); data = grant_input(operation=operation)
    first = grant(access_env, data=data)
    second = grant(access_env, data=data)
    assert second == first and first.expires_at == 5600
    subject = service.subject(sessions[0].bearer, users[2])
    item = next(value for value in subject.permissions if value.permission == "plans.write")
    assert item.managed and item.expires_at == 5600

def test_same_operation_with_changed_payload_is_conflict(access_env):
    operation = uuid4(); first = grant_input(operation=operation)
    grant(access_env, data=first)
    changed = grant_input(operation=operation, ttl=7200)
    with pytest.raises(AuthError, match="idempotency_conflict"):
        grant(access_env, data=changed)


@pytest.mark.parametrize("field,value", [
    ("permission", "root.everything"), ("scope", "project"),
    ("ttl_seconds", 299), ("ttl_seconds", 30*24*60*60+1), ("ttl_seconds", "3600")])
def test_input_is_bounded(field, value):
    payload = grant_input().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        GrantAccessInput.model_validate(payload)


def test_unmanaged_permission_cannot_be_adopted_by_http(access_env):
    service, users, sessions = access_env
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(accounts.permissions).values(
            account_id=users[2], permission="catalog.read", expires_at=9000))
    with pytest.raises(AuthError, match="unmanaged_permission"):
        grant(access_env, data=grant_input("catalog.read"))


def test_self_delegation_is_forbidden(access_env):
    service, users, sessions = access_env
    with pytest.raises(AuthError, match="self_delegation_forbidden"):
        service.grant(sessions[0].bearer, sessions[0].view.csrf_token, users[0],
            grant_input("plans.read"), "fixture")

def test_ceiling_is_required_and_bounds_expiry(access_env):
    service, users, sessions = access_env
    with service.auth.engine.begin() as conn:
        conn.execute(sa.delete(access_tables.ceilings).where(
            access_tables.ceilings.c.account_id == users[0],
            access_tables.ceilings.c.permission == "plans.write"))
    with pytest.raises(AuthError, match="delegation_forbidden"):
        grant(access_env)
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(access_tables.ceilings).values(account_id=users[0],
            permission="plans.write", scope="global", granted_by=None,
            created_at=2000, expires_at=2600))
    with pytest.raises(AuthError, match="delegation_too_long"):
        grant(access_env, data=grant_input(ttl=3600))


def test_revoke_removes_materialized_permission_and_replays(access_env):
    service, users, sessions = access_env
    grant(access_env)
    operation = uuid4(); data = revoke_input(operation=operation)
    first = revoke(access_env, data=data)
    second = revoke(access_env, data=data)
    assert second == first and first.action == "revoke"
    assert all(item.permission != "plans.write" for item in
               service.subject(sessions[0].bearer, users[2]).permissions)
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(accounts.permissions).where(
            accounts.permissions.c.account_id == users[2],
            accounts.permissions.c.permission == "plans.write")).first() is None

def test_sensitive_state_rechecked_after_password_verification(access_env, monkeypatch):
    service, users, sessions = access_env
    original = service._fresh_proof
    def race(*args, **kwargs):
        proof = original(*args, **kwargs)
        with service.auth.engine.begin() as conn:
            conn.execute(sa.delete(accounts.permissions).where(
                accounts.permissions.c.account_id == users[0],
                accounts.permissions.c.permission == "access.manage"))
        return proof
    monkeypatch.setattr(service, "_fresh_proof", race)
    with pytest.raises(AuthError, match="forbidden"):
        grant(access_env)
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(accounts.permissions).where(
            accounts.permissions.c.account_id == users[2],
            accounts.permissions.c.permission == "plans.write")).first() is None


def test_wrong_password_never_mutates_access(access_env):
    with pytest.raises(AuthError, match="reauth_required"):
        grant(access_env, data=grant_input(password="wrong-password"))
    service, users, _ = access_env
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(access_tables.operations)).first() is None


def test_access_manage_requires_read_for_same_lifetime(access_env):
    service, users, sessions = access_env
    grant(access_env, data=grant_input("access.read", ttl=3600))
    with pytest.raises(AuthError, match="access_read_required"):
        grant(access_env, data=grant_input("access.manage", ttl=7200))
    grant(access_env, data=grant_input("access.manage", ttl=3600))
    with pytest.raises(AuthError, match="access_manage_requires_read"):
        revoke(access_env, data=revoke_input("access.read"))


def test_finite_manager_does_not_replace_last_permanent_owner(access_env):
    service, users, sessions = access_env
    grant(access_env, target=1, data=grant_input("access.read"))
    grant(access_env, target=1, data=grant_input("access.manage"))
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(access_tables.ceilings).values(account_id=users[1],
            permission="access.manage", scope="global", granted_by=None,
            created_at=2000, expires_at=5600))
    with pytest.raises(AuthError, match="last_access_owner"):
        service.revoke(sessions[1].bearer, sessions[1].view.csrf_token, users[0],
            revoke_input("access.manage"), "fixture")


def test_second_permanent_owner_allows_owner_rotation(access_env):
    service, users, sessions = access_env
    service.enroll_local_owner(users[1], OWNER_EFFECTIVE)
    receipt = service.revoke(sessions[1].bearer, sessions[1].view.csrf_token, users[0],
        revoke_input("access.manage"), "fixture")
    assert receipt.action == "revoke"
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(accounts.permissions).where(
            accounts.permissions.c.account_id == users[0],
            accounts.permissions.c.permission == "access.manage")).first() is None
        assert conn.execute(sa.select(access_tables.ceilings).where(
            access_tables.ceilings.c.account_id == users[1],
            access_tables.ceilings.c.permission == "access.manage",
            access_tables.ceilings.c.expires_at.is_(None))).first() is not None


def test_admin_me_surfaces_access_read_for_a28_navigation(access_env):
    service, users, sessions = access_env
    view = AdminService(service.auth).me(sessions[0].bearer)
    assert "access.read" in view.permissions
    assert "access.manage" not in view.permissions
