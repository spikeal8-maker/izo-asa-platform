"""Denials and revocation must apply to metadata, quota and bytes, not just UI."""
import sqlalchemy as sa
import pytest
from izo.accounts import tables as a
from izo.entitlements.schemas import PlanPolicy, PublishPlan, SetDefault
from izo.entitlements.service import EntitlementService
from izo.media import tables as t
from test_media import env, start, finish, failure
from uuid import uuid4


def new_policy(env, **kw):
    svc, users, _, engine, _ = env
    with engine.begin() as conn:
        ps = EntitlementService(clock=svc.auth.clock)
        pub = PublishPlan(operation_id=uuid4(), reason='synthetic policy change', revision_id=uuid4(),
            plan_code='basic', revision=2, policy=PlanPolicy(**kw))
        ps.publish(conn, users[0].view.account.id, pub)
        ps.set_default(conn, users[0].view.account.id, SetDefault(operation_id=uuid4(),
            reason='synthetic default', revision_id=pub.revision_id, expected_version=1))


@pytest.mark.parametrize('policy,code', [({},'upload_not_allowed'),
    ({'input_count':2,'upload_bytes':1,'storage_bytes':1000000},'upload_too_large'),
    ({'input_count':2,'upload_bytes':1000,'storage_bytes':1000},'storage_quota_exceeded')])
def test_zero_missing_or_too_small_limits_deny(env, policy, code):
    new_policy(env, **policy)
    failure(code, lambda: start(env))
    assert env[0].list(env[1][0].bearer).reserved_bytes == 0


def test_existing_allocations_count_against_quota(env):
    new_policy(env, input_count=2, upload_bytes=1000, storage_bytes=100000)
    first, _, _ = start(env)
    failure('storage_quota_exceeded', lambda: start(env))
    user = env[1][0]
    env[0].cancel(user.bearer, user.view.csrf_token, first.id)
    assert start(env)[0].status == 'pending'


def test_pending_cap_and_creation_rate(env):
    for _ in range(4): start(env)
    failure('upload_limit', lambda: start(env))


def test_plan_reduction_does_not_hide_files_or_abandon_committed_reserve(env):
    svc, users, *_ = env
    user = users[0]
    complete, _, _ = finish(env)
    pending, _, data = start(env)
    new_policy(env)
    assert svc.get(user.bearer, complete.id).byte_size > 0
    assert svc.submit(user.bearer, user.view.csrf_token, pending.id, data).status == 'ready'
    failure('upload_not_allowed', lambda: start(env))


@pytest.mark.parametrize('state', ['generation_suspended','deletion_pending','security_locked','deleted'])
def test_restricted_account_cannot_create_upload(env, state):
    svc, users, _, engine, _ = env
    with engine.begin() as conn:
        conn.execute(sa.update(a.accounts).where(a.accounts.c.id==users[0].view.account.id).values(state=state))
    failure('account_restricted' if state in {'generation_suspended','deletion_pending'} else 'auth_required', lambda: start(env))


def test_unverified_and_bad_csrf_cannot_create_upload(env):
    svc, users, _, engine, _ = env
    upload, command, _ = start(env)
    user = users[0]
    failure('csrf_rejected', lambda: svc.begin(user.bearer, 'x'*43, command))
    with engine.begin() as conn:
        conn.execute(sa.update(a.identities).where(a.identities.c.account_id==user.view.account.id).values(verified_at=None))
    failure('verification_required', lambda: start(env))


def test_download_token_bound_to_asset_session_and_expiry(env):
    svc, users, clock, engine, _ = env
    user = users[0]
    ready, _, _ = finish(env)
    grant = svc.ticket(user.bearer, user.view.csrf_token, ready.id)
    secret = grant.url.split('ticket=')[1]
    assert svc.download(user.bearer, ready.id, secret).startswith(b'\x89PNG')
    failure('not_found', lambda: svc.download(users[1].bearer, ready.id, secret))
    with engine.begin() as conn:
        row = svc.auth._session(conn, user.bearer)[0]
        second = svc.auth._new_session(conn, row, 'second browser', clock[0])
    failure('not_found', lambda: svc.download(second.bearer, ready.id, secret))
    clock[0] += 121
    failure('not_found', lambda: svc.download(user.bearer, ready.id, secret))
    assert svc.get(user.bearer, ready.id).id == ready.id


def test_ticket_is_hashed_and_download_keeps_no_billing_requirement(env):
    svc, users, _, engine, _ = env
    user = users[0]
    ready, _, _ = finish(env)
    grant = svc.ticket(user.bearer, user.view.csrf_token, ready.id)
    secret = grant.url.split('ticket=')[1]
    with engine.begin() as conn:
        text = str(conn.execute(sa.select(t.tickets)).all())
        assert secret not in text and len(text) > 64
        conn.execute(sa.update(a.accounts).where(a.accounts.c.id==user.view.account.id).values(state='generation_suspended'))
    assert svc.download(user.bearer, ready.id, secret).startswith(b'\x89PNG')


def test_revoked_session_during_storage_read_never_receives_bytes(env):
    svc, users, _, _, store = env
    user = users[0]
    ready, _, _ = finish(env)
    secret = svc.ticket(user.bearer, user.view.csrf_token, ready.id).url.split('ticket=')[1]
    store.on_read = lambda: svc.auth.revoke(user.bearer, user.view.csrf_token)
    failure('auth_required', lambda: svc.download(user.bearer, ready.id, secret))


def test_changed_or_missing_object_is_not_served(env):
    svc, users, _, _, store = env
    user = users[0]
    ready, _, _ = finish(env)
    secret = svc.ticket(user.bearer, user.view.csrf_token, ready.id).url.split('ticket=')[1]
    key = next(iter(store.data))
    original = store.data[key]
    store.data[key] = b'x'*len(original)
    failure('media_integrity_error', lambda: svc.download(user.bearer, ready.id, secret))
    store.data.pop(key)
    failure('media_unavailable', lambda: svc.download(user.bearer, ready.id, secret))


def test_pagination_and_unknown_ids(env):
    svc, users, *_ = env
    for _ in range(3): finish(env)
    first = svc.list(users[0].bearer, 2)
    second = svc.list(users[0].bearer, 2, first.next_offset)
    assert len(first.assets)==2 and len(second.assets)==1 and second.next_offset is None
    assert {a.id for a in first.assets}.isdisjoint({a.id for a in second.assets})
    failure('not_found', lambda: svc.get(users[0].bearer, uuid4()))
    failure('invalid_input', lambda: svc.list(users[0].bearer, 100))
