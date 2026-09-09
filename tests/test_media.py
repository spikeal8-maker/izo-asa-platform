"""Private image lifecycle on isolated SQL, with genuine Accounts/Entitlements."""
import hashlib
import io
from uuid import uuid4

import pytest
import sqlalchemy as sa
from PIL import Image, PngImagePlugin
from pydantic import ValidationError
from izo.accounts import tables as a, media_access
from izo.accounts.schemas import RegisterInput
from izo.accounts.security import AuthError
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.entitlements.schemas import PlanPolicy, PublishPlan, SetDefault
from izo.entitlements.service import EntitlementService
from izo.entitlements import tables as e
from izo.credits import tables as c
from izo.media import tables as t, codec
from izo.media.schemas import UploadIntent, MediaError
from izo.media.service import MediaService


class MemoryStore:
    def __init__(self):
        self.data, self.failure = {}, None
        self.on_read = None

    def put(self, key, data, content_type):
        assert content_type == 'image/png' and key.endswith('/image.png')
        if self.failure == 'before':
            raise OSError('synthetic private storage detail')
        self.data[key] = data
        if self.failure == 'after':
            raise OSError('synthetic private storage detail')

    def read(self, key, maximum):
        if self.on_read:
            self.on_read()
        data = self.data[key]
        if len(data) > maximum:
            raise OSError('bounded object read')
        return data


def image_bytes(fmt='PNG', size=(8, 6), metadata=False):
    stream = io.BytesIO()
    with Image.new('RGB', size, (60, 80, 100)) as image:
        kw = {}
        if metadata:
            text = PngImagePlugin.PngInfo()
            text.add_text('private', 'do-not-publish-this-metadata')
            kw['pnginfo'] = text
        image.save(stream, format=fmt, **kw)
    return stream.getvalue()


def intent(data, **kw):
    fields = dict(operation_id=uuid4(), content_type='image/png', byte_size=len(data),
                  sha256=hashlib.sha256(data).hexdigest(), width=8, height=6)
    return UploadIntent(**(fields | kw))


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = sa.create_engine('sqlite:///' + str(tmp_path/'media.sqlite'),
                              connect_args={'check_same_thread': False})
    @sa.event.listens_for(engine, 'connect')
    def pragma(db, record):
        db.isolation_level = None
        db.execute('PRAGMA foreign_keys=ON')
    @sa.event.listens_for(engine, 'begin')
    def begin(conn):
        conn.exec_driver_sql('BEGIN')
    a.metadata.create_all(engine)
    t.metadata.create_all(engine, tables=list(t.TABLES))
    clock = [2000]
    auth = AuthService(engine, AuthSettings(registration='invite', rate_secret='x'*40,
        login_limit=100, network_limit=1000), clock=lambda: clock[0])
    users = []
    for n in range(2):
        user = auth.register(RegisterInput(email=f'upload-{n}@example.invalid',
            display_name=f'Synthetic {n}', password='test-media-password-only',
            invite_code=auth.issue_invite()), 'isolated-peer', 'test')
        users.append(user)
    with engine.begin() as conn:
        conn.execute(sa.update(a.identities).values(verified_at=2000))
        conn.execute(sa.insert(a.permissions).values(account_id=users[0].view.account.id, permission='plans.write'))
        conn.execute(sa.insert(e.defaults).values(id=1, version=0))
        plans = EntitlementService(clock=auth.clock)
        command = PublishPlan(operation_id=uuid4(), reason='isolated fixture', revision_id=uuid4(),
            plan_code='basic', revision=1, policy=PlanPolicy(storage_bytes=10_000_000,
                upload_bytes=1_000_000, input_count=4))
        plans.publish(conn, users[0].view.account.id, command)
        plans.set_default(conn, users[0].view.account.id, SetDefault(operation_id=uuid4(),
            reason='isolated fixture', revision_id=command.revision_id, expected_version=0))
    store = MemoryStore()
    monkeypatch.setattr(codec, 'decode', codec.rewrite)
    yield MediaService(auth, store), users, clock, engine, store
    engine.dispose()


def start(env, data=None, **kw):
    service, users, *_ = env
    user = users[0]
    data = data or image_bytes()
    command = intent(data, **kw)
    upload = service.begin(user.bearer, user.view.csrf_token, command)
    return upload, command, data


def finish(env, data=None, **kw):
    upload, command, data = start(env, data, **kw)
    user = env[1][0]
    result = env[0].submit(user.bearer, user.view.csrf_token, upload.id, data)
    return result, command, data


def failure(code, call):
    with pytest.raises((MediaError, AuthError)) as exc:
        call()
    assert exc.value.code == code


def test_upload_rewrite_owner_gallery_and_no_billing(env):
    svc, users, clock, engine, store = env
    user, other = users
    result, _, original = finish(env, image_bytes(metadata=True))
    assert result.status == 'ready' and result.reserved_bytes == 0
    gallery = svc.list(user.bearer)
    assert len(gallery.assets) == 1 and gallery.reserved_bytes == 0
    assert svc.list(other.bearer).assets == []
    asset = svc.get(user.bearer, result.id)
    downloaded = next(iter(store.data.values()))
    assert asset.sha256 == hashlib.sha256(downloaded).hexdigest()
    assert b'do-not-publish' not in downloaded and downloaded != original
    with Image.open(io.BytesIO(downloaded)) as im:
        im.load()
        assert im.mode == 'RGBA' and im.size == (8, 6) and not im.info
    with engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(c.ledger)).scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(c.wallets)).scalar_one() == 0


def test_replay_has_one_reservation_asset_and_audit(env):
    svc, users, _, engine, _ = env
    user = users[0]
    upload, command, data = start(env)
    assert svc.begin(user.bearer, user.view.csrf_token, command).id == upload.id
    assert svc.list(user.bearer).reserved_bytes == command.storage_bound()
    result = svc.submit(user.bearer, user.view.csrf_token, upload.id, data)
    assert svc.submit(user.bearer, user.view.csrf_token, upload.id, data) == result
    assert svc.complete(user.bearer, user.view.csrf_token, upload.id) == result
    with engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.assets)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(a.audit).where(a.audit.c.action=='media.finalized')).scalar_one() == 1
    changed = command.model_copy(update={'width': 9})
    failure('idempotency_conflict', lambda: svc.begin(user.bearer, user.view.csrf_token, changed))


@pytest.mark.parametrize('action', ['status','get','submit','cancel','complete','ticket'])
def test_other_user_cannot_access_even_known_id(env, action):
    result, _, data = finish(env)
    svc, users, *_ = env
    other = users[1]
    args = [other.bearer]
    if action not in {'get','status'}:
        args.append(other.view.csrf_token)
    args.append(result.id)
    if action == 'submit':
        args.append(data)
    failure('not_found', lambda: getattr(svc, action)(*args))


@pytest.mark.parametrize('change,code', [({'byte_size':0},None), ({'width':False},None),
    ({'sha256':'abc'},None), ({'content_type':'image/svg+xml'},None),
    ({'width':8192,'height':8192},None), ({'account_id':str(uuid4())},None)])
def test_intent_rejects_untrusted_or_unbounded_fields(change, code):
    with pytest.raises(ValidationError):
        intent(image_bytes(), **change)


@pytest.mark.parametrize('change', [{'content_type':'image/jpeg'}, {'width':9}])
def test_declared_type_and_dimensions_are_not_trusted(env, change):
    svc, users, *_ = env
    upload, _, data = start(env, **change)
    user = users[0]
    # Isolated rewrite reports ValueError; production child maps it to invalid_image.
    monkey = pytest.MonkeyPatch()
    def safe_decode(*args):
        try: return codec.rewrite(*args)
        except Exception: raise MediaError(422, 'invalid_image') from None
    monkey.setattr(codec, 'decode', safe_decode)
    try:
        failure('invalid_image', lambda: svc.submit(user.bearer, user.view.csrf_token, upload.id, data))
        assert svc.status(user.bearer, upload.id).status == 'rejected'
        assert svc.list(user.bearer).reserved_bytes == 0
    finally:
        monkey.undo()


def test_mismatched_checksum_does_not_write_or_consume_intent(env):
    svc, users, *_ = env
    upload, _, data = start(env)
    user = users[0]
    failure('upload_content_mismatch', lambda: svc.submit(user.bearer, user.view.csrf_token, upload.id, data+b'x'))
    assert svc.status(user.bearer, upload.id).status == 'pending'
    assert not env[-1].data


@pytest.mark.parametrize('mode', ['before','after'])
def test_uncertain_store_retains_reservation_and_same_intent_recovers(env, mode):
    svc, users, clock, engine, store = env
    upload, command, data = start(env)
    user = users[0]
    store.failure = mode
    failure('storage_write_uncertain', lambda: svc.submit(user.bearer, user.view.csrf_token, upload.id, data))
    assert svc.status(user.bearer, upload.id).status == 'storing'
    assert svc.list(user.bearer).reserved_bytes == command.storage_bound()
    failure('upload_requires_reconciliation', lambda: svc.cancel(user.bearer, user.view.csrf_token, upload.id))
    store.failure = None
    result = (svc.complete(user.bearer, user.view.csrf_token, upload.id) if mode=='after'
              else svc.submit(user.bearer, user.view.csrf_token, upload.id, data))
    assert result.status == 'ready' and len(store.data) == 1
    assert svc.list(user.bearer).reserved_bytes == 0


def test_finalize_audit_failure_rolls_back_asset_and_keeps_recovery(env, monkeypatch):
    svc, users, _, engine, store = env
    user = users[0]
    upload, _, data = start(env)
    original = media_access.record
    def broken(conn, p, action, aid):
        if action == 'media.finalized':
            raise RuntimeError('synthetic audit failure')
        return original(conn, p, action, aid)
    monkeypatch.setattr(media_access, 'record', broken)
    with pytest.raises(RuntimeError):
        svc.submit(user.bearer, user.view.csrf_token, upload.id, data)
    assert svc.status(user.bearer, upload.id).status == 'storing' and len(store.data)==1
    assert svc.list(user.bearer).assets == []
    monkeypatch.setattr(media_access, 'record', original)
    assert svc.complete(user.bearer, user.view.csrf_token, upload.id).status == 'ready'


def test_cancel_fences_a_validating_attempt(env):
    svc, users, *_ = env
    user = users[0]
    upload, _, data = start(env)
    row, attempt = svc.claim(user.bearer, user.view.csrf_token, upload.id, data)
    result = svc.cancel(user.bearer, user.view.csrf_token, upload.id)
    image = codec.rewrite(data, 'image/png', 8, 6, row['reserved_bytes'])
    failure('stale_upload_attempt', lambda: svc.seal(user.bearer, user.view.csrf_token, upload.id, attempt, image))
    assert result.status == 'cancelled' and result.reserved_bytes == 0


def test_expired_intent_releases_only_unwritten_allocation(env):
    svc, users, clock, *_ = env
    user = users[0]
    upload, _, data = start(env)
    clock[0] += 901
    assert svc.status(user.bearer, upload.id).status == 'expired'
    assert svc.list(user.bearer).reserved_bytes == 0
    failure('upload_closed', lambda: svc.submit(user.bearer, user.view.csrf_token, upload.id, data))


def test_stale_validation_cannot_seal_after_another_attempt(env):
    svc, users, clock, *_ = env
    user = users[0]
    upload, _, data = start(env)
    row, old = svc.claim(user.bearer, user.view.csrf_token, upload.id, data)
    clock[0] += 61
    _, new = svc.claim(user.bearer, user.view.csrf_token, upload.id, data)
    assert old != new
    image = codec.rewrite(data, 'image/png', 8, 6, row['reserved_bytes'])
    failure('stale_upload_attempt', lambda: svc.seal(user.bearer, user.view.csrf_token, upload.id, old, image))


def test_concurrent_claim_is_busy_until_lease(env):
    svc, users, *_ = env
    user = users[0]
    upload, _, data = start(env)
    svc.claim(user.bearer, user.view.csrf_token, upload.id, data)
    failure('upload_busy', lambda: svc.submit(user.bearer, user.view.csrf_token, upload.id, data))


def test_unknown_write_is_not_expired_or_released(env):
    svc, users, clock, _, store = env
    user = users[0]
    upload, command, data = start(env)
    store.failure = 'after'
    failure('storage_write_uncertain', lambda: svc.submit(user.bearer, user.view.csrf_token, upload.id, data))
    clock[0] += 901
    assert svc.status(user.bearer, upload.id).status == 'storing'
    assert svc.list(user.bearer).reserved_bytes == command.storage_bound()
    assert svc.complete(user.bearer, user.view.csrf_token, upload.id).status == 'ready'
