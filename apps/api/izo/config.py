"""Configuration only: no connection, directory creation or worker startup."""
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IZO_", extra="ignore", hide_input_in_errors=True
    )
    environment: Literal["development", "test"] = "development"
    pg_host: str = "postgres"
    pg_port: int = Field(default=5432, ge=1, le=65535)
    pg_database: str = "izo"
    pg_user: str = "izo"
    pg_password: SecretStr = SecretStr("")
    s3_endpoint: str = "http://storage:8333"
    s3_region: str = "us-east-1"
    s3_bucket: str = "izo-private"
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    build_sha: str = Field(default="unreleased", pattern=r"^(unreleased|[a-f0-9]{40})$")

    @model_validator(mode="after")
    def validate_storage(self):
        # urlsplit alone does not validate ports; parser errors can echo input.
        try:
            u = urlsplit(self.s3_endpoint)
            invalid = (
                any(c.isspace() or ord(c) < 32 for c in self.s3_endpoint)
                or u.scheme not in {"http", "https"}
                or not u.hostname or u.username is not None or u.password is not None
                or u.query or u.fragment or u.path not in {"", "/"}
                or u.netloc.endswith(":")
                or (u.port is not None and not 1 <= u.port <= 65535)
            )
        except ValueError:
            invalid = True
        if invalid:
            raise ValueError("Invalid S3 endpoint; credentials belong in secret settings") from None
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
