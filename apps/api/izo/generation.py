"""Pure routing and state transition policy; not a durable worker implementation."""
from collections.abc import Sequence
from .contracts import Capability, Executor, JobSpec, JobState

ALLOWED = {
    JobState.QUEUED: {JobState.CLAIMED, JobState.CANCELLED},
    JobState.CLAIMED: {JobState.RUNNING, JobState.FAILED, JobState.CANCELLED,
                       JobState.RECONCILING},
    JobState.RUNNING: {JobState.UPLOADING, JobState.FAILED, JobState.RECONCILING},
    JobState.UPLOADING: {JobState.SUCCEEDED, JobState.FAILED, JobState.RECONCILING},
    JobState.RECONCILING: {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED},
    JobState.SUCCEEDED: set(), JobState.FAILED: set(), JobState.CANCELLED: set(),
}


def transition(current: JobState, target: JobState) -> JobState:
    if target not in ALLOWED[current]:
        raise ValueError(f"Invalid transition: {current} -> {target}")
    return target


def pool_for(job: JobSpec) -> str:
    return f"{job.executor.value}:{job.modality.value}"


def resolve_capability(catalog: Sequence[Capability], capability_id: str,
                       *, local_available: bool) -> Capability:
    ids = [c.id for c in catalog]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate capability id")
    result = next((c for c in catalog if c.id == capability_id), None)
    if result is None or not result.enabled:
        raise ValueError("Capability unavailable")
    if result.executor == Executor.LOCAL and not local_available:
        raise ValueError("Local executor unavailable")
    return result
