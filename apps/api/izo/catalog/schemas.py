"""CATALOG-001 typed admin contracts. Raw secrets and arbitrary endpoints are absent."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

Version = int
Resolution = Literal["512", "1K", "2K", "4K"]
SourceType = Literal["env", "secret_file", "secret_manager"]
Environment = Literal["development", "test"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True,
        revalidate_instances="always", hide_input_in_errors=True)


class Reasoned(StrictModel):
    operation_id: UUID
    expected_version: int = Field(strict=True, ge=0, le=2_000_000_000)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def meaningful_reason(self):
        if not self.reason.strip() or any(ord(c) < 32 for c in self.reason):
            raise ValueError("Reason required")
        return self


class CapabilityDraft(Reasoned):
    name: str = Field(min_length=1, max_length=120)
    help: str = Field(default="", max_length=2000)
    adapter_id: Literal["openrouter.images.v1"] = "openrouter.images.v1"
    model_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,120}/[A-Za-z0-9_.:-]{1,160}$")
    connection_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{0,79}$")
    resolutions: tuple[Resolution, ...] = Field(default=(), max_length=4)
    price_credits: int = Field(default=0, strict=True, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def unique_resolutions(self):
        if len(set(self.resolutions)) != len(self.resolutions):
            raise ValueError("Duplicate resolutions")
        return self


class ConnectionDraft(Reasoned):
    account_ref: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    project_ref: str | None = Field(default=None, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    environment: Environment
    max_concurrency: int = Field(default=0, strict=True, ge=0, le=64)
    rate_limit: int = Field(default=0, strict=True, ge=0, le=1_000_000)
    rate_window_seconds: int = Field(default=60, strict=True, ge=1, le=86_400)
    spend_cap_minor: int = Field(default=0, strict=True, ge=0, le=1_000_000_000)
    currency: Literal["USD"] = "USD"
    timeout_seconds: int = Field(default=180, strict=True, ge=30, le=600)
    allow_fallbacks: bool = False


class CredentialBind(Reasoned):
    source_type: SourceType
    secret_ref: str = Field(min_length=1, max_length=200)
    environment: Environment
    account_ref: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    project_ref: str | None = Field(default=None, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    current_password: SecretStr

    @field_validator("secret_ref")
    @classmethod
    def safe_reference(cls, value):
        if any(ord(c) < 33 or c.isspace() for c in value) or ".." in value or value.startswith(("http:", "https:")):
            raise ValueError("Invalid secret reference")
        return value

    @model_validator(mode="after")
    def source_reference_policy(self):
        # CATALOG stores a logical locator, never a secret value or arbitrary
        # filesystem path. Runtime resolver policy is a later package.
        if self.source_type == "env":
            valid = self.secret_ref == "IZO_OPENROUTER_API_KEY"
        elif self.source_type == "secret_file":
            valid = bool(__import__("re").fullmatch(r"openrouter/[A-Za-z0-9_.:-]{1,80}", self.secret_ref))
        else:
            valid = bool(__import__("re").fullmatch(r"vault/izo/openrouter/[A-Za-z0-9_.:-]{1,80}", self.secret_ref))
        if not valid:
            raise ValueError("Unapproved logical secret reference")
        return self


class RevokeCredential(Reasoned):
    current_password: SecretStr


class ProofInput(Reasoned):
    connection_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{0,79}$")
    connection_version: int = Field(strict=True, ge=0, le=2_000_000_000)


class PublishInput(Reasoned):
    proof_id: UUID


class DisableInput(Reasoned):
    pass


class RevisionView(StrictModel):
    id: UUID
    revision: int
    content_hash: str
    created_at: int


class CapabilityContent(StrictModel):
    name: str
    help: str
    adapter_id: str
    model_id: str
    connection_id: str
    resolutions: tuple[Resolution, ...]
    price_credits: int


class CapabilityView(StrictModel):
    capability_id: str
    version: int
    draft: RevisionView | None
    published: RevisionView | None
    content: CapabilityContent | None
    runtime_available: Literal[False] = False


class ConnectionContent(StrictModel):
    provider_id: Literal["openrouter"] = "openrouter"
    endpoint: Literal["https://openrouter.ai/api/v1/images"] = "https://openrouter.ai/api/v1/images"
    account_ref: str
    project_ref: str | None
    environment: Environment
    max_concurrency: int
    rate_limit: int
    rate_window_seconds: int
    spend_cap_minor: int
    currency: Literal["USD"]
    timeout_seconds: int
    allow_fallbacks: bool


class CredentialView(StrictModel):
    binding_id: UUID
    version: int
    source_type: SourceType
    reference_fingerprint: str
    environment: Environment
    account_ref: str
    project_ref: str | None
    state: Literal["active", "revoked"]
    created_at: int
    revoked_at: int | None


class ConnectionView(StrictModel):
    connection_id: str
    version: int
    draft: RevisionView | None
    published: RevisionView | None
    content: ConnectionContent | None
    runtime_state: Literal["disabled"] = "disabled"
    credential: CredentialView | None


class ProofView(StrictModel):
    proof_id: UUID
    capability_id: str
    connection_id: str
    capability_hash: str
    connection_hash: str
    credential_version: int
    evidence_hash: str
    proof_kind: Literal["contract"] = "contract"
    network_called: Literal[False] = False
    live_ready: Literal[False] = False
    created_at: int


class ChangeReceipt(StrictModel):
    operation_id: UUID
    action: str
    target: str
    result_version: int
    result_id: UUID | None


class CapabilityList(StrictModel):
    items: tuple[CapabilityView, ...]


class ConnectionList(StrictModel):
    items: tuple[ConnectionView, ...]


class ProviderView(StrictModel):
    provider_id: Literal["openrouter"] = "openrouter"
    adapter_id: Literal["openrouter.images.v1"] = "openrouter.images.v1"
    endpoint: Literal["https://openrouter.ai/api/v1/images"] = "https://openrouter.ai/api/v1/images"
    live_enabled: Literal[False] = False


class ProviderList(StrictModel):
    items: tuple[ProviderView, ...] = (ProviderView(),)


class CatalogError(Exception):
    def __init__(self, status: int, code: str, fields: tuple[str, ...] = ()):
        super().__init__(code)
        self.status, self.code, self.fields = status, code, fields
