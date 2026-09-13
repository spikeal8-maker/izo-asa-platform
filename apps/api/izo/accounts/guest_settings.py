"""Server-owned bounded guest-trial policy."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .security import AuthError


class GuestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IZO_GUEST_", extra="ignore")
    enabled: bool = False
    session_seconds: int = Field(default=3600, ge=300, le=86400)
    network_limit: int = Field(default=3, ge=1, le=20)
    rate_window: int = Field(default=86400, ge=3600, le=604800)
    trial_credits: int = Field(default=1, ge=1, le=3)
    trial_width: int = Field(default=512, ge=64, le=512)
    trial_height: int = Field(default=512, ge=64, le=512)

    def require_enabled(self) -> None:
        if not self.enabled:
            raise AuthError(503, "guest_disabled")

    @staticmethod
    def cookie_name(secure: bool) -> str:
        return "__Host-izo_guest" if secure else "izo_dev_guest"
