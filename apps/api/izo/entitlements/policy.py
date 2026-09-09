"""Pure IMAGE admission preview. No DB/network and no resource reservation.

Usage and runtime are server-owned snapshots, NEVER client input. A positive
preview is not a ticket to dispatch: JOBS must recheck and reserve atomically.
"""
from uuid import UUID
from typing import Literal
from pydantic import Field

from .schemas import (StrictModel, EntitlementView, CapabilityId, Executor,
                      Count, Bytes, Credits, Epoch, ImageSize)


class ImageDemand(StrictModel):
    capability_id: CapabilityId
    executor: Executor
    size: ImageSize
    input_count: int = Field(strict=True, ge=0, le=32)
    largest_input_bytes: Bytes
    output_bytes_bound: int = Field(strict=True, ge=1, le=1_000_000_000)
    reserve_credits: Credits


class RuntimeState(StrictModel):
    feature_enabled: bool
    capability_supported: bool
    provider_available: bool


class UsageSnapshot(StrictModel):
    account_id: UUID
    as_of: Epoch
    window_seconds: int = Field(strict=True, ge=1, le=86400)
    active_jobs: Count
    submissions: Count
    committed_bytes: Bytes
    reserved_bytes: Bytes


class PolicyDecision(StrictModel):
    allowed: bool
    code: str
    revision_id: UUID | None
    policy_hash: str | None
    # Explicitly NOT an allocation/authorization receipt usable by a worker.
    admission_reserved: Literal[False] = False


def evaluate(view: EntitlementView, demand: ImageDemand, runtime: RuntimeState,
             usage: UsageSnapshot | None, available_credits: int) -> PolicyDecision:
    view = EntitlementView.model_validate(view)
    demand = ImageDemand.model_validate(demand)
    runtime = RuntimeState.model_validate(runtime)
    if usage is not None:
        usage = UsageSnapshot.model_validate(usage)

    def result(code):
        return PolicyDecision(allowed=code == "allowed", code=code,
                              revision_id=view.revision_id, policy_hash=view.policy_hash)

    if view.account_state != "active":
        return result("account_restricted")
    if not view.identity_verified:
        return result("verification_required")
    if not runtime.feature_enabled:
        return result("feature_unavailable")
    p = view.policy
    if not view.configured or p is None:
        return result("plan_unconfigured")
    if demand.capability_id not in p.capability_ids or demand.executor not in p.executors:
        return result("plan_restricted")
    if not runtime.capability_supported:
        return result("capability_unsupported")
    if not runtime.provider_available:
        return result("provider_unavailable")
    if demand.size not in p.image_sizes:
        return result("image_size_restricted")
    if demand.input_count > p.input_count or demand.largest_input_bytes > p.upload_bytes:
        return result("input_limit")
    if (demand.input_count == 0) != (demand.largest_input_bytes == 0):
        return result("invalid_input_usage")
    if demand.reserve_credits > p.max_action_credits:
        return result("action_budget_exceeded")
    if (usage is None or usage.account_id != view.account_id
            or usage.as_of != view.as_of or usage.window_seconds != p.window_seconds):
        return result("usage_unavailable")
    if usage.active_jobs >= p.active_jobs:
        return result("concurrency_limit")
    if usage.submissions >= p.submissions:
        return result("rate_limited")
    if usage.committed_bytes + usage.reserved_bytes + demand.output_bytes_bound > p.storage_bytes:
        return result("storage_quota_exceeded")
    if type(available_credits) is not int or available_credits < 0:
        return result("balance_unavailable")
    if available_credits < demand.reserve_credits:
        return result("insufficient_credits")
    return result("allowed")
