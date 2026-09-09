"""MEDIA-001 API contracts with real session resolution and isolated SQL/storage."""
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from izo.media.routes import attach_media
from test_media import env, image_bytes, intent


@pytest.fixture
def client(env):
    svc, users, _, _, store = env
    app = FastAPI()
    app.state.media_store = store
    attach_media(app, lambda request: svc.auth, None)
    with TestClient(app) as client:
        client.cookies.set(svc.auth.policy.cookie_name, users[0].bearer)
        client.headers.update({'Origin':'http://localhost:8080','X-IZO-Request':'web',
                               'X-CSRF-Token':users[0].view.csrf_token})
        yield client


def upload(client):
    data=image_bytes(metadata=True)
    r=client.post('/api/v1/media/uploads',json=intent(data).model_dump(mode='json'))
    assert r.status_code==201, r.text
    uid=r.json()['id']
    r=client.post(f'/api/v1/media/uploads/{uid}/content',content=data,
                  headers={'Content-Type':'application/octet-stream'})
    assert r.status_code==200 and r.json()['status']=='ready', r.text
    return uid


def test_real_session_upload_list_and_protected_binary(client):
    uid=upload(client)
    result=client.get('/api/v1/media/assets')
    assert result.status_code==200 and len(result.json()['assets'])==1
    assert 'object_key' not in result.text and 'assets/' not in result.text
    link=client.post(f'/api/v1/media/assets/{uid}/download',json={}).json()['url']
    response=client.get(link)
    assert response.status_code==200 and response.content.startswith(b'\x89PNG')
    assert response.headers['content-type']=='image/png'
    assert 'attachment' in response.headers['content-disposition']
    assert 'no-store' in response.headers['cache-control']
    assert response.headers['x-content-type-options']=='nosniff'
    assert 'sandbox' in response.headers['content-security-policy']
    assert b'do-not-publish' not in response.content


@pytest.mark.parametrize('headers,status', [({'Origin':'https://untrusted.invalid'},403),
    ({'X-IZO-Request':'other'},403),({'X-CSRF-Token':'x'*43},403),
    ({'Sec-Fetch-Site':'cross-site'},403),({'Content-Encoding':'gzip'},415)])
def test_upload_cannot_bypass_origin_csrf_encoding(client, headers,status):
    r=client.post('/api/v1/media/uploads', json=intent(image_bytes()).model_dump(mode='json'),headers=headers)
    assert r.status_code==status
    assert client.get('/api/v1/media/assets').json()['reserved_bytes']==0


@pytest.mark.parametrize('suffix', ['?account_id=PRIVATE_VALUE','?limit=20&limit=20','?limit=1000'])
def test_query_injection_and_validation_do_not_echo_input(client,suffix):
    r=client.get('/api/v1/media/assets'+suffix)
    assert r.status_code==422 and 'PRIVATE_VALUE' not in r.text


def test_missing_or_revoked_session_cannot_read(client,env):
    uid=upload(client)
    client.cookies.clear()
    assert client.get(f'/api/v1/media/assets/{uid}').status_code==401
    user=env[1][0]
    env[0].auth.revoke(user.bearer,user.view.csrf_token)
    client.cookies.set(env[0].auth.policy.cookie_name,user.bearer)
    assert client.get(f'/api/v1/media/assets/{uid}').status_code==401


def test_json_body_is_bounded_before_parsing(client):
    r=client.post('/api/v1/media/uploads',content=b'x'*8193,headers={'Content-Type':'application/json'})
    assert r.status_code==413 and 'input' not in r.text


def test_malformed_uuid_and_schema_are_redacted(client):
    r=client.get('/api/v1/media/assets/PRIVATE_VALUE')
    assert r.status_code==422 and 'PRIVATE_VALUE' not in r.text
    r=client.post('/api/v1/media/uploads',json={'password':'PRIVATE_VALUE'})
    assert r.status_code==422 and 'PRIVATE_VALUE' not in r.text


def test_no_public_or_arbitrary_url_upload(client):
    r=client.post('/api/v1/media/uploads',json=intent(image_bytes()).model_dump(mode='json')|{'url':'http://127.0.0.1/private'})
    assert r.status_code==422
    assert client.post('/api/v1/media/assets',json={}).status_code==405


def test_no_input_body_is_used_as_ready_asset(client):
    r=client.post('/api/v1/media/uploads',json=intent(image_bytes()).model_dump(mode='json'))
    uid=r.json()['id']
    assert client.get(f'/api/v1/media/assets/{uid}').status_code==404
    assert client.post(f'/api/v1/media/uploads/{uid}/complete',json={}).status_code==409


def test_base_auth_origin_semantics_are_preserved():
    from izo.accounts.http_security import same_origin
    from izo.accounts.security import AuthError
    from types import SimpleNamespace
    from starlette.datastructures import Headers
    auth=SimpleNamespace(policy=SimpleNamespace(origins=('http://localhost:8080',)))
    request=SimpleNamespace(headers=Headers({'origin':'http://localhost:8080','x-izo-request':'web',
                                            'content-type':'application/json'}))
    same_origin(request,auth)
    request.headers=Headers({'origin':'http://localhost:8080','x-izo-request':'web',
                             'content-type':'application/octet-stream'})
    with pytest.raises(AuthError) as exc: same_origin(request,auth)
    assert exc.value.code=='json_required'
    same_origin(request,auth,content_type='application/octet-stream')
