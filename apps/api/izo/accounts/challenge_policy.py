"""Test delivery only; separate proof secret, no SMTP configuration or live fallback."""
import base64
import hashlib
import hmac
import re
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from .security import AuthError

PROOF = re.compile(r"^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$")


class ChallengeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IZO_RECOVERY_", extra="ignore", hide_input_in_errors=True)
    delivery: str = Field(default="disabled", pattern="^(disabled|test)$")
    secret: SecretStr = SecretStr("")
    ttl_seconds: int = Field(default=600, ge=60, le=1800)
    max_attempts: int = Field(default=5, ge=1, le=10)
    request_limit: int = Field(default=3, ge=1, le=10)

    def require_enabled(self):
        if self.delivery != "test" or len(self.secret.get_secret_value()) < 32:
            raise AuthError(503, "recovery_not_configured")

    def proof(self, challenge_id: UUID, purpose: str) -> str:
        self.require_enabled()
        # Random UUID selector; HMAC supplies 256-bit secret proof. The database
        # stores only its hash. A separate secret allows restart-safe test mail
        # rendering without persisting recoverable bearer tokens or adding crypto.
        message = f"izo:email-proof:v1:{purpose}:{challenge_id.hex}".encode("ascii")
        digest = hmac.new(self.secret.get_secret_value().encode(), message, hashlib.sha256).digest()
        return challenge_id.hex + "." + base64.urlsafe_b64encode(digest).decode().rstrip("=")


def selector(value: str) -> UUID:
    if not PROOF.fullmatch(value):
        raise AuthError(400, "invalid_challenge")
    return UUID(hex=value[:32])


def binding(account) -> str:
    value = f"{account['id']}\0{account['email']}\0{account['password_hash']}".encode()
    return hashlib.sha256(value).hexdigest()
