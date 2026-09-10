"""Split public routing settings from the worker-only credential."""
import json
import re
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Resolution = Literal["512", "1K", "2K", "4K"]
_RESOLUTION_PIXELS = {"512": 512, "1K": 1024, "2K": 2048, "4K": 4096}


class OpenRouterSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IZO_OPENROUTER_", extra="ignore",
                                      hide_input_in_errors=True)
    enabled: bool = False
    model: str = ""
    price_credits: int = Field(default=0, ge=0, le=1_000_000)
    resolutions: tuple[Resolution, ...] = ()
    timeout_seconds: int = Field(default=180, ge=30, le=600)
    connection_id: str = "openrouter-primary"
    allow_fallbacks: bool = False

    @field_validator("model")
    @classmethod
    def model_slug(cls, value):
        if value and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}/[A-Za-z0-9_.:-]{1,160}", value):
            raise ValueError("Invalid OpenRouter model slug")
        return value

    @field_validator("connection_id")
    @classmethod
    def connection_slug(cls, value):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,79}", value):
            raise ValueError("Invalid connection ID")
        return value

    @model_validator(mode="after")
    def enabled_is_complete(self):
        if self.enabled and (not self.model or self.price_credits <= 0 or not self.resolutions):
            raise ValueError("Enabled OpenRouter image connection requires model, price and resolutions")
        if len(set(self.resolutions)) != len(self.resolutions):
            raise ValueError("Duplicate OpenRouter resolutions")
        return self

    def supports(self, width: int, height: int) -> str | None:
        if width != height:
            return None
        for resolution in self.resolutions:
            if _RESOLUTION_PIXELS[resolution] == width:
                return resolution
        return None

    def execution_snapshot(self, width: int, height: int) -> dict:
        resolution = self.supports(width, height)
        if not self.enabled or resolution is None:
            raise ValueError("OpenRouter image capability unavailable")
        return {
            "version": 1,
            "adapter": "openrouter.images.v1",
            "connection_id": self.connection_id,
            "model": self.model,
            "resolution": resolution,
            "output_format": "png",
            "allow_fallbacks": self.allow_fallbacks,
            "price_credits": self.price_credits,
        }


class OpenRouterSecret(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IZO_OPENROUTER_", extra="ignore",
                                      hide_input_in_errors=True)
    api_key: SecretStr = SecretStr("")

    def require(self) -> str:
        value = self.api_key.get_secret_value()
        if not value or len(value) < 16 or any(c.isspace() for c in value):
            raise ValueError("OpenRouter worker credential unavailable")
        return value


def parse_execution(raw: str | None) -> dict:
    if not raw or len(raw) > 4096:
        raise ValueError("Missing provider execution snapshot")
    value = json.loads(raw)
    expected = {"version", "adapter", "connection_id", "model", "resolution",
                "output_format", "allow_fallbacks", "price_credits"}
    if set(value) != expected or value["version"] != 1 or value["adapter"] != "openrouter.images.v1":
        raise ValueError("Invalid provider execution snapshot")
    if value["resolution"] not in _RESOLUTION_PIXELS or value["output_format"] != "png":
        raise ValueError("Invalid provider image contract")
    if type(value["price_credits"]) is not int or value["price_credits"] <= 0:
        raise ValueError("Invalid provider price snapshot")
    OpenRouterSettings(model=value["model"], connection_id=value["connection_id"])
    return value
