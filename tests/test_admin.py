"""ADMIN-001 real domain services on SQLite; PG races are separate acceptance."""
from uuid import uuid4
import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from izo.accounts import tables as a, repository as ar, admin_access
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.accounts.security import AuthError, hash_password
from izo.credits.schemas import CreditError
from izo.credits import tables as c
from izo.admin import tables as t
from izo.admin.schemas import CompensationInput
from izo.admin.service import AdminService

PASSWORD = "Synthetic-admin-test-password-2026"


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def admin_env(tmp_path, password_hash):
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "admin.sqlite"),
                              connect_args={"check_same_thread": False})
    @sa.event.listens_for(engine, "connect")
    def configure(conn, record):
        conn.isolation_level = None
        conn.execute("PRAGMA foreign_keys=ON")
    @sa.event.listens_for(engine, "begin")
    def begin(conn):
        conn.exec_driver_sql("BEGIN")
    a.metadata.create_all(engine)
    auth = AuthService(engine, AuthSettings(registration="invite", rate_secret="x"*40,
                         login_limit=100), clock=lambda: 2000)
    users, sessions = [], []
    with engine.begin() as conn:
        for name in ["Operator", "ReadOnly", "Recipient", "Other"]:
            uid, iid = uuid4(), uuid4()
            users.append(uid)
            conn.execute(sa.insert(a.accounts).values(id=uid, public_code=uid.hex[:16],
                        display_name=name, state="active", created_at=1000))
            conn.execute(sa.insert(a.identities).values(id=iid, account_id=uid,
                        provider="email", subject=uid.hex+"@example.invalid", verified_at=1000))
            conn.execute(sa.insert(a.passwords).values(identity_id=iid, password_hash=password_hash))
            sessions.append(auth._new_session(conn, ar.account_by_id(conn, uid), "fixture", 2000))
        conn.execute(sa.insert(a.permissions).values(account_id=users[1], permission="users.read_limited"))
    service = AdminService(auth)
    service.enroll_local_operator(users[0], 1000)
    yield service, users, sessions
    engine.dispose()


def command(**kwargs):
    return CompensationInput(**{ "operation_id": uuid4(), "case_reference": "CASE-"+uuid4().hex,
         "amount": 100, "current_password": PASSWORD, **kwargs })


def compensate(env, data=None, user=0, target=2):
    service, users, sessions = env
    return service.compensate(sessions[user].bearer, sessions[user].view.csrf_token,
                              users[target], data or command(), "fixture")


def test_server_balance_and_exact_retry(admin_env):
    service, users, sessions = admin_env
    data = command()
    first = compensate(admin_env, data)
    assert compensate(admin_env, data) == first
    own = service.credits_view(sessions[0].bearer, users[2])
    assert own.balance.available == 100 and len(own.entries) == 1
    with service.auth.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.events).where(
            t.events.c.action == "compensation.granted")).scalar_one() == 1
        assert service.credits.reconcile(conn, users[2]).consistent


def test_business_case_survives_new_operation_key(admin_env):
    data = command(case_reference=" ext-123 ")
    compensate(admin_env, data)
    with pytest.raises(CreditError, match="source_already_used"):
        compensate(admin_env, command(case_reference="EXT-123"))
    with pytest.raises(CreditError, match="source_already_used"):
        compensate(admin_env, command(case_reference="EXT-123"), target=3)


@pytest.mark.parametrize("field,value", [("amount",101), ("case_reference","DIFFERENT")])
def test_same_operation_different_payload_rejected(admin_env, field, value):
    data = command()
    compensate(admin_env, data)
    with pytest.raises((AuthError, CreditError), match="idempotency_conflict"):
        compensate(admin_env, command(**{**data.model_dump(),field:value}))


def test_operation_cannot_move_to_another_account(admin_env):
    data = command()
    compensate(admin_env, data)
    with pytest.raises(AuthError, match="idempotency_conflict"):
        compensate(admin_env, data, target=3)


@pytest.mark.parametrize("amount", [0,-1,1.2,True,"100",1000000001])
def test_strict_amounts(amount):
    with pytest.raises(ValidationError):
        command(amount=amount)


@pytest.mark.parametrize("ref", ["ab", "user@example.invalid", "a/b", "../..", "a"*65, "Имя"])
def test_case_references_are_bounded_identifiers(ref):
    with pytest.raises(ValidationError):
        command(case_reference=ref)


@pytest.mark.parametrize("field", ["actor_id","grant_limit","role","reason","provider"])
def test_caller_cannot_choose_privilege(field):
    with pytest.raises(ValidationError):
        command(**{field: "forged"})


@pytest.mark.parametrize("permission", ["credits.grant", "credits.read", "users.read_limited"])
def test_missing_or_revoked_permissions(admin_env, permission):
    service, users, sessions = admin_env
    with service.auth.engine.begin() as conn:
        conn.execute(sa.delete(a.permissions).where(a.permissions.c.account_id == users[0],
                                                      a.permissions.c.permission == permission))
    with pytest.raises(AuthError, match="forbidden"):
        compensate(admin_env)


@pytest.mark.parametrize("kind", ["expired","zero","missing"])
def test_finite_policy_required(admin_env, kind):
    service, users, sessions = admin_env
    with service.auth.engine.begin() as conn:
        query = sa.update(t.policies).where(t.policies.c.account_id == users[0])
        if kind == "missing":
            conn.execute(sa.delete(t.policies))
        else:
            conn.execute(query.values(**({"expires_at":2000} if kind=="expired" else {"max_grant":0})))
    assert service.me(sessions[0].bearer).max_grant == 0
    with pytest.raises(CreditError, match="grant_forbidden"):
        compensate(admin_env)


def test_over_cap_and_wrong_password_do_not_change_balance(admin_env):
    with pytest.raises(CreditError, match="grant_forbidden"):
        compensate(admin_env, command(amount=1001))
    with pytest.raises(AuthError, match="reauth_required"):
        compensate(admin_env, command(current_password="incorrect"))
    service, users, sessions = admin_env
    assert service.credits_view(sessions[0].bearer, users[2]).balance.available == 0


def test_read_only_staff_has_no_financial_access(admin_env):
    service, users, sessions = admin_env
    assert service.user(sessions[1].bearer, users[2]).display_name == "Recipient"
    assert service.me(sessions[1].bearer).max_grant == 0
    with pytest.raises(AuthError, match="forbidden"):
        service.credits_view(sessions[1].bearer, users[2])
    with pytest.raises(AuthError, match="forbidden"):
        service.audit(sessions[1].bearer)
    with pytest.raises(AuthError, match="forbidden"):
        compensate(admin_env, user=1)


@pytest.mark.parametrize("state", ["generation_suspended","deletion_pending","security_locked","deleted"])
def test_restricted_staff_denied(admin_env, state):
    service, users, sessions = admin_env
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(a.accounts).where(a.accounts.c.id==users[0]).values(state=state))
    with pytest.raises(AuthError):
        compensate(admin_env)


def test_unverified_staff_denied(admin_env):
    service, users, sessions = admin_env
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(a.identities).where(a.identities.c.account_id==users[0]).values(verified_at=None))
    with pytest.raises(AuthError, match="verification_required"):
        compensate(admin_env)


def test_audit_failure_rolls_back_every_credit_change(admin_env, monkeypatch):
    service, users, sessions = admin_env
    def fail(*args, **kwargs):
        raise RuntimeError("fixture_audit_failure")
    monkeypatch.setattr(service, "_event", fail)
    with pytest.raises(RuntimeError, match="fixture_audit_failure"):
        compensate(admin_env)
    with service.auth.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(c.ledger)).scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(c.wallets)).scalar_one() == 0


@pytest.mark.parametrize("change", ["password","session","permission","policy"])
def test_sensitive_state_rechecked_after_password_verification(admin_env, monkeypatch, change):
    service, users, sessions = admin_env
    original = admin_access.reauthenticate
    def race(*args, **kwargs):
        proof = original(*args, **kwargs)
        with service.auth.engine.begin() as conn:
            if change == "password":
                iid=conn.execute(sa.select(a.identities.c.id).where(a.identities.c.account_id==users[0])).scalar_one()
                conn.execute(sa.update(a.passwords).where(a.passwords.c.identity_id==iid).values(password_hash="changed"))
            elif change == "session":
                conn.execute(sa.update(a.sessions).where(a.sessions.c.account_id==users[0]).values(revoked_at=2000))
            elif change == "permission":
                conn.execute(sa.delete(a.permissions).where(a.permissions.c.account_id==users[0]))
            else:
                conn.execute(sa.update(t.policies).where(t.policies.c.account_id==users[0]).values(max_grant=0))
        return proof
    monkeypatch.setattr(admin_access, "reauthenticate", race)
    with pytest.raises((AuthError, CreditError)):
        compensate(admin_env)
    with service.auth.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(c.ledger)).scalar_one() == 0


def test_search_paging_and_minimal_fields(admin_env):
    service, users, sessions = admin_env
    result = service.users(sessions[0].bearer, users[2].hex[:16])
    assert [row.id for row in result.users] == [users[2]]
    assert set(result.users[0].model_dump()) == {"id","public_code","display_name","state","created_at","verified"}
    assert service.users(sessions[0].bearer, "%%%_").users == []
    assert service.users(sessions[0].bearer, "operator", limit=1).users[0].id == users[0]


def test_denial_audited_without_password_or_case_payload(admin_env):
    service, users, sessions = admin_env
    with pytest.raises(AuthError):
        compensate(admin_env, command(current_password="wrong"))
    data = service.audit(sessions[0].bearer).model_dump(mode="json")
    assert any(e["outcome"] == "denied" for e in data["events"])
    assert PASSWORD not in str(data) and "password_hash" not in str(data)


def test_old_session_cannot_read_staff_card(admin_env):
    service, users, sessions = admin_env
    service.auth.revoke(sessions[0].bearer,sessions[0].view.csrf_token)
    with pytest.raises(AuthError, match="auth_required"):
        service.user(sessions[0].bearer, users[2])
