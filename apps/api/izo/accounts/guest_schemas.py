"""Small public contract for the anonymous first-run principal."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GuestView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_id: UUID
    csrf_token: str
    expires_at: int
    trial_used: bool
    capability_id: str = "test.image.v1"


class GuestStart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
