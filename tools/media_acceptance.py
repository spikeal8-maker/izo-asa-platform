"""Isolated PostgreSQL/HTTP/S3 acceptance. Synthetic state never enters artifacts."""
import hashlib
import io
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import sqlalchemy as sa
from PIL import Image, PngImagePlugin
from izo.accounts import tables as a
from izo.accounts.repository import create_auth_engine
from izo.accounts.schemas import RegisterInput
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.config import Settings
from izo.credits import tables as credits
from izo.entitlements import tables as plans
from izo.entitlements.schemas import AssignPlan, PlanPolicy, PublishPlan
from izo.entitlements.service import EntitlementService
from izo.media import tables as media
from izo.media.objects import MediaStore
from izo.media.schemas import MediaError, UploadIntent
from izo.media.service import MediaService


def request(auth, user, path, payload=None, binary=False):
    assert path.startswith('/api/v1/') and not path.startswith('//')
    headers = {'Origin': 'http://localhost:8080', 'X-IZO-Request': 'web',
        'Cookie': auth.policy.cookie_name + '=' + user['bearer'],
        'X-CSRF-Token': user['csrf']}
    data = None
    if payload is not None:
        headers['Content-Type'] = 'application/octet-stream' if binary else 'application/json'
        data = payload if binary else json.dumps(payload).encode()
    req = urllib.request.Request('http://api:8000' + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            status, body = response.status, response.read(2 * 1024 * 1024)
            content_type = response.headers.get('Content-Type', '')
    except urllib.error.HTTPError as response:
        status, body = response.code, response.read(8192)
        content_type = response.headers.get('Content-Type', '')
    return status, json.loads(body) if 'application/json' in content_type else body


def checked(auth, user, path, payload=None, *, expected=200, binary=False):
    status, body = request(auth, user, path, payload, binary)
    assert status == expected, f'Media HTTP status {status}, expected {expected}'
    return body


def pixels():
    stream = io.BytesIO()
    text = PngImagePlugin.PngInfo()
    text.add_text('private', 'synthetic-metadata-must-be-removed')
    with Image.new('RGB', (8, 6), (20, 40, 70)) as image:
        image.save(stream, format='PNG', pnginfo=text)
    return stream.getvalue()


def command(data):
    return UploadIntent(operation_id=uuid4(), content_type='image/png',
        byte_size=len(data), sha256=hashlib.sha256(data).hexdigest(), width=8, height=6)


def fixture(auth, data):
    users = []
    for _ in range(3):
        receipt = auth.register(RegisterInput(email=f'media-{uuid4().hex}@example.invalid',
            display_name='Isolated media fixture', password=secrets.token_urlsafe(24),
            invite_code=auth.issue_invite()), 'isolated-media-' + uuid4().hex, 'media-acceptance')
        users.append({'id': str(receipt.view.account.id), 'bearer': receipt.bearer,
                      'csrf': receipt.view.csrf_token})
    actor = UUID(users[0]['id'])
    with auth.engine.begin() as conn:
        conn.execute(sa.update(a.identities).where(a.identities.c.account_id.in_(
            [UUID(user['id']) for user in users])).values(verified_at=auth.now()))
        conn.execute(sa.insert(a.permissions).values(account_id=actor, permission='plans.write'))
        revision = conn.execute(sa.select(sa.func.coalesce(sa.func.max(plans.revisions.c.revision), 0))
            .where(plans.revisions.c.plan_code == 'custom')).scalar_one()
        service = EntitlementService(clock=auth.clock)
        # Do not change the global basic pointer tested by preceding stages.
        for index, user in enumerate(users):
            storage = command(data).storage_bound() if index == 2 else 5_000_000
            policy = PublishPlan(operation_id=uuid4(), revision_id=uuid4(),
                reason='isolated media fixture', plan_code='custom', revision=revision + index + 1,
                policy=PlanPolicy(storage_bytes=storage, upload_bytes=min(1_000_000, storage), input_count=2))
            service.publish(conn, actor, policy)
            service.assign(conn, actor, UUID(user['id']), AssignPlan(operation_id=uuid4(),
                reason='isolated media fixture', revision_id=policy.revision_id,
                expected_version=0, starts_at=auth.now(), expires_at=auth.now() + 7200))
    return users


def before(auth, config):
    data = pixels()
    owner, other, racer = fixture(auth, data)
    intent = command(data).model_dump(mode='json')
    record = checked(auth, owner, '/api/v1/media/uploads', intent, expected=201)
    assert checked(auth, owner, '/api/v1/media/uploads', intent, expected=201) == record
    upload_path = '/api/v1/media/uploads/' + record['id']
    checked(auth, other, upload_path, expected=404)
    result = checked(auth, owner, upload_path + '/content', data, binary=True)
    assert result['status'] == 'ready'
    asset_path = '/api/v1/media/assets/' + record['id']
    asset = checked(auth, owner, asset_path)
    checked(auth, other, asset_path, expected=404)
    ticket = checked(auth, owner, asset_path + '/download', {})
    rewritten = checked(auth, owner, ticket['url'])
    assert hashlib.sha256(rewritten).hexdigest() == asset['sha256']
    assert b'synthetic-metadata' not in rewritten
    checked(auth, other, ticket['url'], expected=404)
    with auth.engine.begin() as conn:
        conn.execute(sa.update(media.tickets).where(media.tickets.c.asset_id == UUID(record['id']))
                     .values(expires_at=auth.now() - 1))
    checked(auth, owner, ticket['url'], expected=404)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: request(auth, racer, '/api/v1/media/uploads',
            command(data).model_dump(mode='json'))[0], range(2)))
    assert sorted(outcomes) == [201, 409], 'Concurrent uploads exceeded storage reservation'

    class UncertainStore(MediaStore):
        def put(self, key, value, content_type):
            super().put(key, value, content_type)
            raise OSError('synthetic response loss after successful S3 write')

    uncertain = MediaService(auth, UncertainStore(config))
    pending = uncertain.begin(owner['bearer'], owner['csrf'], command(data))
    try:
        uncertain.submit(owner['bearer'], owner['csrf'], pending.id, data)
        raise AssertionError('Expected unknown write outcome')
    except MediaError as error:
        assert error.code == 'storage_write_uncertain'
    assert uncertain.status(owner['bearer'], pending.id).status == 'storing'
    with auth.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(credits.ledger).where(
            credits.ledger.c.account_id == UUID(owner['id']))).scalar_one() == 0
    print('MEDIA_BEFORE_OK: owner HTTP, PNG sanitization, quota race, expired ticket and durable uncertain S3 write', file=sys.stderr)
    print(json.dumps({'owner': owner, 'other': other, 'ready': record['id'],
        'pending': str(pending.id), 'asset_hash': asset['sha256'], 'expired_url': ticket['url']}))


def after(auth):
    state = json.load(sys.stdin)
    owner, other = state['owner'], state['other']
    asset_path = '/api/v1/media/assets/' + state['ready']
    assert checked(auth, owner, asset_path)['sha256'] == state['asset_hash']
    checked(auth, other, asset_path, expected=404)
    checked(auth, owner, state['expired_url'], expected=404)
    path = '/api/v1/media/uploads/' + state['pending']
    assert checked(auth, owner, path)['status'] == 'storing'
    recovered = checked(auth, owner, path + '/complete', {})
    assert recovered['status'] == 'ready'
    assert checked(auth, owner, path + '/complete', {}) == recovered
    listing = checked(auth, owner, '/api/v1/media/assets')
    assert len(listing['assets']) == 2 and listing['reserved_bytes'] == 0
    assert listing['used_bytes'] == sum(asset['byte_size'] for asset in listing['assets'])
    ticket = checked(auth, owner, asset_path + '/download', {})
    assert hashlib.sha256(checked(auth, owner, ticket['url'])).hexdigest() == state['asset_hash']
    with auth.engine.begin() as conn:
        count = conn.execute(sa.select(sa.func.count()).select_from(a.audit).where(
            a.audit.c.account_id == UUID(owner['id']), a.audit.c.action == 'media.finalized')).scalar_one()
        assert count == 2
    checked(auth, owner, '/api/v1/auth/logout', {}, expected=204)
    checked(auth, owner, ticket['url'], expected=401)
    print('MEDIA_AFTER_OK: assets/allocations survive Compose restart; stored result recovered once; revoke closes downloads')


def main():
    if os.environ.get('IZO_MEDIA_ACCEPTANCE') != 'isolated' or os.environ.get('IZO_ENVIRONMENT') != 'test':
        raise SystemExit('Only explicitly enabled disposable test infrastructure is allowed')
    if len(sys.argv) != 2 or sys.argv[1] not in {'before', 'after'}:
        raise SystemExit('Use before or after')
    config = Settings()
    if config.pg_host != 'postgres' or config.s3_endpoint != 'http://storage:8333':
        raise SystemExit('Only standard isolated Compose dependencies are allowed')
    engine = create_auth_engine(config)
    try:
        auth = AuthService(engine, AuthSettings())
        before(auth, config) if sys.argv[1] == 'before' else after(auth)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
