"""API-001 contract tests. No live OpenRouter request and no production secret."""
import base64
import io
import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from PIL import Image
from pydantic import ValidationError

from izo.entitlements.schemas import PlanPolicy, ImageSize, PublishPlan, SetDefault
from izo.entitlements.service import EntitlementService
from izo.jobs import catalog, tables as jobs
from izo.jobs.catalog import JobSettings
from izo.jobs.schemas import QuoteInput, CreateJob, JobError
from izo.jobs.service import JobService
from izo.jobs.execution import JobRunner
from izo.jobs.recovery import reconcile_one
from izo.media.service import MediaService
from izo.providers.openrouter.client import generate, ProviderError, ProviderImage, ENDPOINT, NoRedirect
from izo.providers.openrouter.config import OpenRouterSettings, OpenRouterSecret, parse_execution
from izo.providers.openrouter import worker
from test_jobs import env, balances


def png(size=512):
    out = io.BytesIO()
    Image.new("RGB", (size, size), "black").save(out, format="PNG")
    return out.getvalue()


def enabled(**kwargs):
    return OpenRouterSettings(enabled=True, model="google/gemini-2.5-flash-image",
        price_credits=3, resolutions=("512",), **kwargs)


def grant_openrouter(env):
    service, _, users, *_ = env
    actor = users[0].view.account.id
    plans = EntitlementService(clock=service.auth.clock)
    with service.auth.engine.begin() as conn:
        current = plans.resolve(conn, actor)
        revision = uuid4()
        policy = PlanPolicy.model_validate(current.policy.model_dump() | {
            "capability_ids": ("test.image.v1", "openrouter.image.v1"),
            "image_sizes": (ImageSize(width=64, height=64), ImageSize(width=512, height=512)),
            "max_action_credits": 3,
        })
        plans.publish(conn, actor, PublishPlan(operation_id=uuid4(), revision_id=revision,
            plan_code="basic", revision=current.revision + 1, policy=policy, reason="api001 test"))
        plans.set_default(conn, actor, SetDefault(operation_id=uuid4(), revision_id=revision,
            expected_version=current.default_version, reason="api001 test"))
    return service, users


def test_openrouter_is_fail_closed_without_complete_operator_config():
    assert not OpenRouterSettings().enabled
    for kwargs in ({"enabled": True}, {"enabled": True, "model": "bad"},
                   {"enabled": True, "model": "x/y", "price_credits": 1}):
        with pytest.raises(ValidationError):
            OpenRouterSettings(**kwargs)
    with pytest.raises(ValueError):
        OpenRouterSecret(api_key="short").require()


def test_execution_snapshot_is_small_strict_and_contains_no_key():
    snapshot = enabled().execution_snapshot(512, 512)
    assert snapshot["adapter"] == "openrouter.images.v1"
    assert snapshot["resolution"] == "512" and snapshot["price_credits"] == 3
    assert "key" not in json.dumps(snapshot).lower()
    assert parse_execution(json.dumps(snapshot)) == snapshot
    with pytest.raises(ValueError):
        parse_execution(json.dumps(snapshot | {"api_key": "secret"}))


def test_client_sends_only_fixed_endpoint_and_decodes_one_bounded_image():
    raw = png()
    captured = {}
    class Response:
        headers = {"Content-Length": "100"}
        def read(self, _):
            return json.dumps({"id": "gen-1", "data": [{"b64_json": base64.b64encode(raw).decode(),
                "media_type": "image/png"}], "usage": {"cost": "0.0123"}}).encode()
    def opener(request, timeout):
        captured.update(url=request.full_url, timeout=timeout, auth=request.get_header("Authorization"),
                        body=json.loads(request.data))
        return Response()
    result = generate(enabled().execution_snapshot(512,512), "safe prompt", "test-secret-key-value",
                      timeout=90, opener=opener)
    assert captured["url"] == ENDPOINT and captured["timeout"] == 90
    assert captured["auth"] == "Bearer test-secret-key-value"
    assert captured["body"] == {"model":"google/gemini-2.5-flash-image", "prompt":"safe prompt",
        "resolution":"512", "output_format":"png", "n":1,
        "provider":{"allow_fallbacks":False}}
    assert result.data == raw and result.cost_usd == Decimal("0.0123") and result.provider_ref == "gen-1"


@pytest.mark.parametrize("payload", [
    {}, {"data": []}, {"data": [{"b64_json": "not-base64", "media_type": "image/png"}]},
    {"data": [{"b64_json": base64.b64encode(b"x").decode(), "media_type": "text/html"}]},
])
def test_invalid_provider_response_is_ambiguous_not_success(payload):
    class Response:
        headers = {}
        def read(self, _): return json.dumps(payload).encode()
    with pytest.raises(ProviderError) as failure:
        generate(enabled().execution_snapshot(512,512), "prompt", "test-secret-key-value",
                 timeout=30, opener=lambda *_args, **_kwargs: Response())
    assert failure.value.request_may_have_completed


def test_quote_freezes_model_price_and_pool_and_config_change_expires_it(env):
    base, users = grant_openrouter(env)
    user = users[0]
    service = JobService(base.auth, JobSettings(enabled=True), enabled())
    draft = QuoteInput(capability_id="openrouter.image.v1", prompt="external test", width=512, height=512)
    quote = service.quote(user.bearer, user.view.csrf_token, draft)
    assert quote.credits == 3 and quote.test_only is False
    with service.auth.engine.connect() as conn:
        row = conn.execute(sa.select(jobs.quotes).where(jobs.quotes.c.id == quote.id)).mappings().one()
        execution = parse_execution(row["execution_json"])
        assert execution["model"] == "google/gemini-2.5-flash-image"
    service.openrouter = OpenRouterSettings(enabled=True, model="openai/gpt-image-1",
        price_credits=3, resolutions=("512",))
    with pytest.raises(JobError, match="quote_expired"):
        service.submit(user.bearer, user.view.csrf_token,
            CreateJob(quote_id=quote.id, operation_id=uuid4()))
    assert balances(env).wallet.reserved == 0


def test_accepted_openrouter_job_keeps_execution_snapshot_and_test_worker_cannot_claim_it(env):
    base, users = grant_openrouter(env)
    user = users[0]
    service = JobService(base.auth, JobSettings(enabled=True), enabled())
    quote = service.quote(user.bearer, user.view.csrf_token,
        QuoteInput(capability_id="openrouter.image.v1", prompt="external test", width=512, height=512))
    command = CreateJob(quote_id=quote.id, operation_id=uuid4())
    job = service.submit(user.bearer, user.view.csrf_token, command)
    assert job.test_only is False and balances(env).wallet.reserved == 3
    assert JobRunner(service, env[4]).claim() is None
    with service.auth.engine.connect() as conn:
        row = conn.execute(sa.select(jobs.jobs).where(jobs.jobs.c.id == job.id)).mappings().one()
        assert row["pool"] == catalog.OPENROUTER_POOL
        assert parse_execution(row["execution_json"])["model"] == "google/gemini-2.5-flash-image"


def test_provider_success_uses_common_media_and_settlement(env, monkeypatch):
    base, users = grant_openrouter(env); user = users[0]
    service = JobService(base.auth, JobSettings(enabled=True), enabled())
    quote = service.quote(user.bearer, user.view.csrf_token,
        QuoteInput(capability_id="openrouter.image.v1", prompt="external test", width=512, height=512))
    job = service.submit(user.bearer, user.view.csrf_token,
        CreateJob(quote_id=quote.id, operation_id=uuid4()))
    runner = JobRunner(service, env[4], "openrouter-test", catalog.OPENROUTER_POOL)
    monkeypatch.setattr(worker, "generate", lambda *a, **k: ProviderImage(png(), "image/png", Decimal("0.02"), "gen-safe"))
    assert worker.execute_one(runner, enabled(), OpenRouterSecret(api_key="test-secret-key-value"))
    final = service.get(user.bearer, job.id)
    assert final.status == "succeeded" and final.charged_credits == 3 and final.asset_id
    assert MediaService(base.auth, env[4]).list(user.bearer).assets[0].id == final.asset_id
    assert balances(env).wallet.available == 97 and balances(env).wallet.reserved == 0
    with base.auth.engine.connect() as conn:
        row = conn.execute(sa.select(jobs.jobs).where(jobs.jobs.c.id == job.id)).mappings().one()
        assert row["provider_ref"] == "gen-safe" and row["provider_cost_usd"] == Decimal("0.020000")


def test_provider_ambiguous_failure_keeps_hold_and_never_auto_requeues(env, monkeypatch):
    base, users = grant_openrouter(env); user = users[0]
    service = JobService(base.auth, JobSettings(enabled=True), enabled())
    quote = service.quote(user.bearer, user.view.csrf_token,
        QuoteInput(capability_id="openrouter.image.v1", prompt="external test", width=512, height=512))
    job = service.submit(user.bearer, user.view.csrf_token,
        CreateJob(quote_id=quote.id, operation_id=uuid4()))
    runner = JobRunner(service, env[4], "openrouter-test", catalog.OPENROUTER_POOL)
    calls = [0]
    def uncertain(*_a, **_k):
        calls[0] += 1
        raise ProviderError("provider_outcome_unknown", request_may_have_completed=True)
    monkeypatch.setattr(worker, "generate", uncertain)
    assert worker.execute_one(runner, enabled(), OpenRouterSecret(api_key="test-secret-key-value"))
    assert calls[0] == 1
    current = service.get(user.bearer, job.id)
    assert current.status == "reconciling" and current.error_code == "provider_outcome_unknown"
    assert balances(env).wallet.reserved == 3 and balances(env).wallet.available == 97
    worker.recover_without_redispatch(runner)
    assert runner.claim() is None and calls[0] == 1


def test_redirect_handler_refuses_cross_origin_redirect_before_key_can_follow():
    handler = NoRedirect()
    request = __import__("urllib.request", fromlist=["Request"]).Request(ENDPOINT, headers={"Authorization": "Bearer secret"})
    assert handler.redirect_request(request, None, 307, "redirect", {}, "https://attacker.invalid/steal") is None


def test_openrouter_pool_does_not_depend_on_test_executor_switch(env):
    base, users = grant_openrouter(env); user = users[0]
    service = JobService(base.auth, JobSettings(enabled=False), enabled())
    quote = service.quote(user.bearer, user.view.csrf_token,
        QuoteInput(capability_id="openrouter.image.v1", prompt="external test", width=512, height=512))
    job = service.submit(user.bearer, user.view.csrf_token,
        CreateJob(quote_id=quote.id, operation_id=uuid4()))
    runner = JobRunner(service, env[4], "openrouter-only", catalog.OPENROUTER_POOL)
    claim = runner.claim()
    assert claim is not None and claim.job_id == job.id


def test_saved_provider_result_reconciles_from_storage_without_second_paid_call(env, monkeypatch):
    base, users = grant_openrouter(env); user = users[0]
    service = JobService(base.auth, JobSettings(enabled=False), enabled())
    quote = service.quote(user.bearer, user.view.csrf_token,
        QuoteInput(capability_id="openrouter.image.v1", prompt="external test", width=512, height=512))
    job = service.submit(user.bearer, user.view.csrf_token,
        CreateJob(quote_id=quote.id, operation_id=uuid4()))
    runner = JobRunner(service, env[4], "openrouter-reconcile", catalog.OPENROUTER_POOL)
    calls = [0]
    def generated(*_a, **_k):
        calls[0] += 1
        return ProviderImage(png(), "image/png", Decimal("0.03"), "gen-preserved")
    monkeypatch.setattr(worker, "generate", generated)
    env[4].failure = "after"
    assert worker.execute_one(runner, enabled(), OpenRouterSecret(api_key="test-secret-key-value"))
    current = service.get(user.bearer, job.id)
    assert current.status == "reconciling" and calls[0] == 1
    with base.auth.engine.connect() as conn:
        row = conn.execute(sa.select(jobs.jobs).where(jobs.jobs.c.id == job.id)).mappings().one()
        assert row["provider_ref"] == "gen-preserved" and row["provider_cost_usd"] == Decimal("0.030000")
    env[4].failure = None
    assert reconcile_one(runner)
    final = service.get(user.bearer, job.id)
    assert final.status == "succeeded" and final.charged_credits == 3 and calls[0] == 1
    with base.auth.engine.connect() as conn:
        row = conn.execute(sa.select(jobs.jobs).where(jobs.jobs.c.id == job.id)).mappings().one()
        assert row["provider_ref"] == "gen-preserved" and row["provider_cost_usd"] == Decimal("0.030000")
    assert balances(env).wallet.available == 97 and balances(env).wallet.reserved == 0
