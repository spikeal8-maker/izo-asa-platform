"""Authentication policy for isolated development/test; no production defaults."""
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IZO_AUTH_", extra="ignore", hide_input_in_errors=True)
    registration: str = Field(default="disabled", pattern="^(disabled|invite)$")
    origins: tuple[str, ...] = ("http://localhost:8080", "http://127.0.0.1:8080")
    secure_cookie: bool = False
    rate_secret: SecretStr = SecretStr("")
    idle_seconds: int = Field(default=1800, ge=60, le=86400)
    absolute_seconds: int = Field(default=604800, ge=900, le=2592000)
    max_sessions: int = Field(default=10, ge=1, le=50)
    login_limit: int = Field(default=5, ge=1, le=100)
    network_limit: int = Field(default=100, ge=1, le=1000)
    rate_window: int = Field(default=300, ge=60, le=3600)

    @model_validator(mode="after")
    def validate_policy(self):
        if self.idle_seconds > self.absolute_seconds or not self.origins:
            raise ValueError("Invalid session policy")
        for origin in self.origins:
            try:
                u = urlsplit(origin)
                port = u.port
                valid = (u.scheme in {"https", "http"} and u.hostname and not u.username
                         and not u.password and not u.path and not u.query and not u.fragment
                         and not any(c.isspace() for c in origin) and not u.netloc.endswith(":"))
                if port is not None and not 1 <= port <= 65535:
                    valid = False
                if u.scheme == "http" and (self.secure_cookie or u.hostname not in {"localhost", "127.0.0.1", "::1"}):
                    valid = False
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Auth origin must be a canonical HTTPS origin or development loopback") from None
        return self

    @property
    def cookie_name(self) -> str:
        return "__Host-izo_session" if self.secure_cookie else "izo_dev_session"

    def require_configured(self) -> None:
        if len(self.rate_secret.get_secret_value()) < 32:
            from .security import AuthError
            raise AuthError(503, "auth_not_configured")
