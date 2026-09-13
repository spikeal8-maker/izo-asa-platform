"""Approved provider/adapter registry. Endpoints and secret locator policies are code-owned."""
from dataclasses import dataclass
import re

from .schemas import CatalogError


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    endpoint: str
    env_secret_ref: str


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    provider_id: str
    model_pattern: str


PROVIDERS = {
    "fal": ProviderSpec(provider_id="fal", endpoint="https://queue.fal.run",
                        env_secret_ref="IZO_FAL_KEY"),
}
ADAPTERS = {
    "fal.images.v1": AdapterSpec(adapter_id="fal.images.v1", provider_id="fal",
        model_pattern=r"^[A-Za-z0-9_.:-]{1,120}/[A-Za-z0-9_.:/-]{1,180}$"),
}
REGISTRY_VERSION = 1


def provider(provider_id: str) -> ProviderSpec:
    try:
        return PROVIDERS[provider_id]
    except KeyError:
        raise CatalogError(422, "provider_unsupported", ("connection.provider_id",)) from None


def adapter(adapter_id: str) -> AdapterSpec:
    try:
        return ADAPTERS[adapter_id]
    except KeyError:
        raise CatalogError(422, "adapter_unsupported", ("capability.adapter_id",)) from None


def validate_model(spec: AdapterSpec, model_id: str) -> None:
    if not re.fullmatch(spec.model_pattern, model_id):
        raise CatalogError(422, "model_unsupported", ("capability.model_id",))


def secret_reference_allowed(provider_id: str, source_type: str, reference: str) -> bool:
    spec = provider(provider_id)
    if source_type == "env":
        return reference == spec.env_secret_ref
    if source_type == "secret_file":
        return bool(re.fullmatch(rf"{re.escape(provider_id)}/[A-Za-z0-9_.:-]{{1,80}}", reference))
    if source_type == "secret_manager":
        return bool(re.fullmatch(rf"vault/izo/{re.escape(provider_id)}/[A-Za-z0-9_.:-]{{1,80}}", reference))
    return False
