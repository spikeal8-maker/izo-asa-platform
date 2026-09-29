"""fal adapter contract tests use fake transport; the default suite never opens network sockets."""
import json
from types import SimpleNamespace
import pytest

from izo.providers.fal import (APP_ID, CONNECTION_ID, CREDENTIAL_REF, QUEUE_ORIGIN,
    FalAdapter, FalAuthRequired, FalPermanent, FalRejected, FalRequestMissing, FalSettings,
    FalSubmissionUnknown, FalTransient, HttpResponse)


class Transport:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError('unexpected transport request')
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


def response(status, value, content_type='application/json'):
    body = value if isinstance(value, bytes) else json.dumps(value).encode()
    return HttpResponse(status, {'Content-Type': content_type}, body)


def settings(**changes):
    values = dict(enabled=True, key='test-secret-never-log', price_microusd_per_mp=5000,
        max_cost_microusd=5000, request_timeout_seconds=5, media_timeout_seconds=5, poll_seconds=1)
    values.update(changes)
    return FalSettings(**values)


def handle_json(request_id='request_12345678'):
    base = f'{QUEUE_ORIGIN}/{APP_ID}/requests/{request_id}'
    return {'request_id':request_id, 'status_url':base+'/status',
            'response_url':base, 'cancel_url':base+'/cancel'}


def test_submit_is_fixed_model_bounded_payload_and_secret_is_header_only():
    transport = Transport([response(200, handle_json())])
    adapter = FalAdapter(settings(), transport)
    draft = SimpleNamespace(prompt='кот в лаборатории', width=64, height=64)
    handle = adapter.submit(draft)
    assert handle.request_id == 'request_12345678'
    method, url, kwargs = transport.calls[0]
    assert method == 'POST' and url == f'{QUEUE_ORIGIN}/{APP_ID}'
    payload = json.loads(kwargs['body'])
    assert payload == {'prompt':'кот в лаборатории', 'image_size':{'width':64,'height':64},
        'num_images':1, 'enable_safety_checker':True, 'output_format':'png'}
    assert kwargs['headers']['Authorization'] == 'Key test-secret-never-log'
    assert kwargs['headers']['X-Fal-Store-IO'] == '0'
    assert kwargs['headers']['X-Fal-Request-Timeout'] == '600'
    assert json.loads(kwargs['headers']['X-Fal-Object-Lifecycle-Preference']) == {
        'expiration_duration_seconds': 3600}
    assert 'test-secret-never-log' not in repr(handle)
    assert adapter.connection_id == CONNECTION_ID and adapter.credential_ref == CREDENTIAL_REF


def test_submit_timeout_is_unknown_and_never_claimed_safe_to_retry():
    adapter = FalAdapter(settings(), Transport([ConnectionError('lost after send')]))
    with pytest.raises(FalSubmissionUnknown, match='provider_submission_unknown'):
        adapter.submit(SimpleNamespace(prompt='x', width=64, height=64))


def test_definite_submit_429_is_rejected_before_acceptance():
    adapter = FalAdapter(settings(), Transport([response(429, {'detail':'limited'})]))
    with pytest.raises(FalRejected, match='provider_rejected'):
        adapter.submit(SimpleNamespace(prompt='x', width=64, height=64))


def test_result_accepts_only_one_matching_png_from_fal_media():
    h = handle_json()
    transport = Transport([
        response(200, {'images':[{'url':'https://v3b.fal.media/files/b/test.png',
            'content_type':'image/png','width':64,'height':64}]}),
        response(200, b'png-bytes', 'image/png'),
    ])
    adapter = FalAdapter(settings(), transport)
    image = adapter.result(adapter.submit if False else SimpleNamespace(**h), width=64, height=64, maximum=1000)
    assert image.data == b'png-bytes' and image.content_type == 'image/png'
    assert transport.calls[1][1].startswith('https://v3b.fal.media/')


def test_result_rejects_ssrf_host_before_media_request():
    h = handle_json()
    transport = Transport([response(200, {'images':[{'url':'https://127.0.0.1/internal.png',
        'content_type':'image/png','width':64,'height':64}]})])
    adapter = FalAdapter(settings(), transport)
    with pytest.raises(FalPermanent, match='provider_invalid_media_url'):
        adapter.result(SimpleNamespace(**h), width=64, height=64, maximum=1000)
    assert len(transport.calls) == 1


def test_budget_is_explicit_and_disabled_by_default(monkeypatch):
    for name in ('IZO_FAL_ENABLED','IZO_FAL_KEY','IZO_FAL_PRICE_MICROUSD_PER_MP','IZO_FAL_MAX_COST_MICROUSD'):
        monkeypatch.delenv(name, raising=False)
    assert not FalSettings().admission_available(64, 64)
    current = settings(max_cost_microusd=20)
    assert current.estimated_cost_microusd(64, 64) == 21
    assert not current.admission_available(64, 64)


def test_known_request_can_be_polled_after_new_admission_is_disabled():
    h = SimpleNamespace(**handle_json())
    disabled = FalSettings(enabled=False, key='test-secret-never-log',
                           price_microusd_per_mp=0, max_cost_microusd=0)
    adapter = FalAdapter(disabled, Transport([response(200, {'status':'COMPLETED'})]))
    assert adapter.status(h).state == 'COMPLETED'


def test_known_request_auth_and_rate_errors_do_not_become_new_submissions():
    h = SimpleNamespace(**handle_json())
    with pytest.raises(FalAuthRequired, match='provider_auth_required'):
        FalAdapter(settings(), Transport([response(401, {})])).status(h)
    with pytest.raises(FalTransient, match='provider_temporarily_unavailable'):
        FalAdapter(settings(), Transport([response(429, {})])).status(h)
    with pytest.raises(FalRequestMissing, match='provider_request_missing'):
        FalAdapter(settings(), Transport([response(404, {})])).status(h)


def test_cancel_contract_distinguishes_requested_completed_and_missing():
    h = SimpleNamespace(**handle_json())
    for http, body, expected in [(202, {'status':'CANCELLATION_REQUESTED'}, 'requested'),
                                 (400, {'status':'ALREADY_COMPLETED'}, 'completed'),
                                 (404, {'status':'NOT_FOUND'}, 'missing')]:
        assert FalAdapter(settings(), Transport([response(http, body)])).cancel(h) == expected


def test_untrusted_queue_operation_url_after_2xx_submit_is_treated_as_unknown_not_retried():
    value = handle_json()
    value['status_url'] = 'https://example.invalid/steal'
    adapter = FalAdapter(settings(), Transport([response(200, value)]))
    with pytest.raises(FalSubmissionUnknown, match='provider_submission_unknown'):
        adapter.submit(SimpleNamespace(prompt='x', width=64, height=64))
