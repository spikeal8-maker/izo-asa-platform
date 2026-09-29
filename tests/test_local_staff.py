"""Exact-account local staff exception and financial boundaries."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.accounts import tables as accounts
from izo.accounts.security import AuthError
from izo.access.permissions import GLOBAL_DELEGABLE, OWNER_EFFECTIVE
from izo.access.service import AccessService
from izo.admin.service import AdminService
from izo.credits import tables as credits
from izo.entitlements.schemas import PlanPolicy
from izo.settings.schemas import PublishInput
from izo.settings.service import SettingsService
from test_access import access_env, grant_input, revoke_input
from test_admin import admin_env, password_hash, compensate


def test_unverified_local_owner_requires_exact_account_opt_in(admin_env, monkeypatch):
    admin, users, sessions = admin_env
    service = AccessService(admin.auth)
    target = users[2]
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(accounts.identities).where(
            accounts.identities.c.account_id == target).values(verified_at=None))

    monkeypatch.delenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", raising=False)
    with pytest.raises(AuthError, match="verified_active_account_required"):
        service.enroll_local_owner(target)
    monkeypatch.setenv("IZO_ENVIRONMENT", "development")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", str(users[1]))
    with pytest.raises(AuthError, match="verified_active_account_required"):
        service.enroll_local_owner(target)
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", str(target))
    monkeypatch.delenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE", raising=False)
    with pytest.raises(AuthError, match="verified_active_account_required"):
        service.enroll_local_owner(target)
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE", "enabled")
    with pytest.raises(AuthError, match="verified_active_account_required"):
        service.enroll_local_owner(target)
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE", "isolated")
    monkeypatch.setenv("IZO_ENVIRONMENT", "production")
    with pytest.raises(AuthError, match="verified_active_account_required"):
        service.enroll_local_owner(target)

    monkeypatch.setenv("IZO_ENVIRONMENT", "development")
    with pytest.raises(AuthError, match="verification_required"):
        service.enroll_local_owner(target)
    safe_permissions = tuple(permission for permission in GLOBAL_DELEGABLE
        if not permission.startswith(("credits.", "plans.")))
    for permission in ("credits.read", "credits.grant", "plans.read", "plans.write"):
        with pytest.raises(AuthError, match="verification_required"):
            service.enroll_local_owner(target, safe_permissions + (permission,))
    service.enroll_local_owner(target, safe_permissions)
    assert "access.manage" in service.me(sessions[2].bearer).permissions
    assert not any(permission.startswith(("credits.", "plans."))
        for permission in service.me(sessions[2].bearer).delegation_ceiling)
    admin_view = AdminService(admin.auth).me(sessions[2].bearer)
    assert "users.read_limited" in admin_view.permissions
    assert "credits.read" not in admin_view.permissions
    assert "credits.grant" not in admin_view.permissions
    with pytest.raises(AuthError, match="forbidden"):
        AdminService(admin.auth).credits_view(sessions[2].bearer, users[1])
    with pytest.raises(AuthError, match="delegation_forbidden"):
        service.grant(sessions[2].bearer, sessions[2].view.csrf_token, users[1],
            grant_input("credits.grant"), "fixture")
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(accounts.identities.c.verified_at).where(
            accounts.identities.c.account_id == target)).scalar_one() is None
    monkeypatch.delenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID")
    with pytest.raises(AuthError, match="verification_required"):
        service.me(sessions[2].bearer)


def test_legacy_owner_loses_financial_access_and_delegation_when_unverified(admin_env, monkeypatch):
    admin, users, sessions = admin_env
    service = AccessService(admin.auth)
    actor, recipient, other = users[2], users[1], users[3]
    service.enroll_local_owner(actor)
    for permission in ("credits.read", "plans.write"):
        service.grant(sessions[2].bearer, sessions[2].view.csrf_token, recipient,
            grant_input(permission), "fixture")
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(accounts.identities).where(
            accounts.identities.c.account_id == actor).values(verified_at=None))
    monkeypatch.setenv("IZO_ENVIRONMENT", "test")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE", "isolated")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", str(actor))
    view = service.me(sessions[2].bearer)
    for values in (view.permissions, view.delegation_ceiling):
        assert not any(permission.startswith(("credits.", "plans.")) for permission in values)
    settings = SettingsService(admin.auth)
    with pytest.raises(AuthError, match="verification_required"):
        settings.view(sessions[2].bearer)
    with pytest.raises(AuthError, match="verification_required"):
        settings.publish(sessions[2].bearer, sessions[2].view.csrf_token,
            PublishInput(operation_id=uuid4(), expected_revision=0,
                policy=PlanPolicy(), reason="local finance guard"))
    for permission in ("credits.read", "plans.write"):
        with pytest.raises(AuthError, match="delegation_forbidden"):
            service.grant(sessions[2].bearer, sessions[2].view.csrf_token, other,
                grant_input(permission), "fixture")
        with pytest.raises(AuthError, match="delegation_forbidden"):
            service.revoke(sessions[2].bearer, sessions[2].view.csrf_token, recipient,
                revoke_input(permission), "fixture")
    with service.auth.engine.connect() as conn:
        rows = set(conn.execute(sa.select(accounts.permissions.c.permission).where(
            accounts.permissions.c.account_id == recipient)).scalars())
        assert {"credits.read", "plans.write"} <= rows


def test_local_staff_exception_requires_an_email_identity(admin_env, monkeypatch):
    admin, users, _ = admin_env
    target = users[2]
    with admin.auth.engine.begin() as conn:
        conn.execute(sa.delete(accounts.identities).where(
            accounts.identities.c.account_id == target))
    monkeypatch.setenv("IZO_ENVIRONMENT", "test")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE", "isolated")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", str(target))
    with pytest.raises(AuthError, match="verified_active_account_required"):
        AccessService(admin.auth).enroll_local_owner(target)


def test_unverified_local_owner_does_not_replace_last_verified_owner(access_env, monkeypatch):
    service, users, sessions = access_env
    target = users[1]
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(accounts.identities).where(
            accounts.identities.c.account_id == target).values(verified_at=None))
    monkeypatch.setenv("IZO_ENVIRONMENT", "test")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE", "isolated")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", str(target))
    service.enroll_local_owner(target, OWNER_EFFECTIVE)
    with pytest.raises(AuthError, match="last_access_owner"):
        service.revoke(sessions[1].bearer, sessions[1].view.csrf_token, users[0],
            revoke_input("access.manage"), "fixture")
    assert "access.manage" in service.me(sessions[1].bearer).permissions


def test_exact_local_staff_opt_in_allows_admin_without_verifying_mailbox(admin_env, monkeypatch):
    service, users, sessions = admin_env
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(accounts.identities).where(
            accounts.identities.c.account_id == users[0]).values(verified_at=None))
    monkeypatch.setenv("IZO_ENVIRONMENT", "development")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE", "isolated")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", str(users[0]))
    view = service.me(sessions[0].bearer)
    assert "users.read_limited" in view.permissions
    assert "credits.read" not in view.permissions
    assert "credits.grant" not in view.permissions
    with pytest.raises(AuthError, match="verification_required"):
        service.credits_view(sessions[0].bearer, users[2])
    with pytest.raises(AuthError, match="verification_required"):
        compensate(admin_env)
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(credits.ledger)).scalar_one() == 0
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(accounts.identities.c.verified_at).where(
            accounts.identities.c.account_id == users[0])).scalar_one() is None
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", str(users[1]))
    with pytest.raises(AuthError, match="verification_required"):
        service.me(sessions[0].bearer)


def test_local_operator_bootstrap_still_requires_verified_mailbox(admin_env, monkeypatch):
    service, users, _ = admin_env
    target = users[2]
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(accounts.identities).where(
            accounts.identities.c.account_id == target).values(verified_at=None))
    monkeypatch.setenv("IZO_ENVIRONMENT", "test")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE", "isolated")
    monkeypatch.setenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", str(target))
    with pytest.raises(AuthError, match="verified_active_account_required"):
        service.enroll_local_operator(target, 100)
