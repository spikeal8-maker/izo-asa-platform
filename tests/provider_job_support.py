"""Shared fixtures for durable external-provider job tests."""
from types import SimpleNamespace
from uuid import uuid4

from izo.entitlements.schemas import PublishPlan, SetDefault
from izo.entitlements.service import EntitlementService
from izo.jobs import catalog
from izo.jobs.execution import JobRunner
from izo.jobs.schemas import QuoteInput, CreateJob
from izo.jobs.service import JobService
from izo.jobs.worker import render_test_image
from izo.providers.fal import (FalHandle, FalImage, FalSettings, FalStatus)
from test_jobs import env, balances


def provider_env(env):
    service, _, users, clock, store = env
    owner = users[0].view.account.id
    plans = EntitlementService(clock=service.auth.clock)
    with service.auth.engine.begin() as conn:
        previous = plans.resolve(conn, owner)
        policy = previous.policy.model_copy(update={
            "capability_ids": tuple(dict.fromkeys(
                previous.policy.capability_ids + (catalog.FAL_CAPABILITY,)))})
        revision = uuid4()
        plans.publish(conn, owner, PublishPlan(operation_id=uuid4(), revision_id=revision,
            plan_code="basic", revision=2, reason="fal isolated fixture", policy=policy))
        plans.set_default(conn, owner, SetDefault(operation_id=uuid4(), revision_id=revision,
            expected_version=previous.default_version, reason="fal isolated fixture"))
    fal = FalSettings(enabled=True, key="synthetic-provider-secret",
        price_microusd_per_mp=5000, max_cost_microusd=5000, poll_seconds=1)
    provider_service = JobService(service.auth, service.policy, fal)
    runner = JobRunner(provider_service, store, "fal-test", pool=catalog.FAL_POOL)
    return provider_service, runner, users, clock, store, fal


def create_provider(env):
    service, runner, users, clock, store, fal = provider_env(env)
    user = users[0]
    draft = QuoteInput(capability_id=catalog.FAL_CAPABILITY,
                       prompt="provider isolation", width=64, height=64)
    quote = service.quote(user.bearer, user.view.csrf_token, draft)
    job = service.submit(user.bearer, user.view.csrf_token,
        CreateJob(quote_id=quote.id, operation_id=uuid4()))
    return service, runner, users, clock, store, fal, draft, job


class FakeAdapter:
    connection_id = "fal-klein-4b-v1"
    credential_ref = "env:IZO_FAL_KEY:v1"

    def __init__(self, draft, statuses=None, *, submit_error=None,
                 on_status=None, on_submit=None):
        self.settings = SimpleNamespace(poll_seconds=0)
        self.draft = draft
        self.statuses = list(statuses or [FalStatus("COMPLETED")])
        self.submit_error = submit_error
        self.on_status = on_status
        self.on_submit = on_submit
        self.submit_count = self.cancel_count = self.status_count = self.result_count = 0
        base = "https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_12345678"
        self.handle = FalHandle("request_12345678", base + "/status", base, base + "/cancel")

    def estimate(self, width, height):
        return 21

    def submit(self, draft):
        self.submit_count += 1
        if self.on_submit:
            self.on_submit(self.submit_count)
        if self.submit_error:
            raise self.submit_error
        return self.handle

    def status(self, handle):
        self.status_count += 1
        if self.on_status:
            self.on_status(self.status_count)
        value = self.statuses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def result(self, handle, **kwargs):
        self.result_count += 1
        return FalImage(render_test_image(self.draft), "image/png")

    def cancel(self, handle):
        self.cancel_count += 1
        return "requested"


__all__ = ["FakeAdapter", "balances", "create_provider", "env", "provider_env"]
