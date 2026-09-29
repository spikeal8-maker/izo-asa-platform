"""Redacted provider failures shared by fixed-origin Chat adapters."""


class ProviderFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def failure(status: int) -> ProviderFailure:
    return ProviderFailure({
        400: "provider_rejected",
        401: "credential_rejected",
        402: "provider_balance",
        403: "credential_rejected",
        422: "model_rejected",
        429: "provider_rate_limited",
        500: "provider_unavailable",
        502: "provider_unavailable",
        503: "provider_overloaded",
        504: "provider_unavailable",
    }.get(status, "provider_error"))
