"""Explicit global permissions ACCESS-001 may delegate; no wildcard roles or object scopes."""

MAX_DELEGATED_SECONDS = 30 * 24 * 60 * 60
MIN_DELEGATED_SECONDS = 5 * 60

GLOBAL_DELEGABLE = (
    "users.read_limited",
    "credits.read",
    "credits.grant",
    "audit.read",
    "access.read",
    "access.manage",
    "plans.read",
    "plans.write",
    "catalog.read",
    "catalog.write",
    "connections.read",
    "connections.write",
    "secrets.bind",
)

KNOWN_GLOBAL = frozenset(GLOBAL_DELEGABLE)
OWNER_EFFECTIVE = ("access.read", "access.manage", "audit.read")
