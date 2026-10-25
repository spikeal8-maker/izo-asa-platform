"""Bounded, isolated fake-provider access via existing Chat admission/Graph."""
import os
from uuid import uuid4

import sqlalchemy as sa
from cryptography.exceptions import InvalidTag

from ..platform_providers import tables as platform
from ..platform_providers.namespace import PLATFORM_NAMESPACE, PLATFORM_ID, AAD_PROVIDER
from ..chat.credential_crypto import encrypt, decrypt
from . import tables as chat
from .credentials import ChatError

PLATFORM_MODEL_PREFIX = "platform:"
SHADOW_PROVIDER = "platform-deepseek"
SHADOW_PLACEHOLDER = "platform-reference-only"


def isolated_platform_demo(config) -> bool:
    return config.environment == "test" and os.getenv("IZO_CHAT_PLATFORM_DEMO") == "isolated"



def _daily_budget(conn, record, now):
    """Single platform row lock serializes quota and concurrency on PostgreSQL."""
    start = now - now % 86400
    row = conn.execute(sa.select(platform.daily_usage).where(
        platform.daily_usage.c.provider == "deepseek",
        platform.daily_usage.c.day_start == start).with_for_update()).mappings().first()
    count = row["requests_admitted"] if row else 0
    if count >= record["daily_limit"]:
        raise ChatError(429, "platform_daily_limit")
    # The fake adapter never posts to a paid provider: confirmed cost is exactly zero.
    if row:
        conn.execute(sa.update(platform.daily_usage).where(
            platform.daily_usage.c.provider == "deepseek",
            platform.daily_usage.c.day_start == start).values(
            requests_admitted=count + 1))
    else:
        conn.execute(sa.insert(platform.daily_usage).values(
            provider="deepseek", day_start=start,
            requests_admitted=1, confirmed_cost_microusd=0))


def _shadow_binding(service, conn, account_id, record, request_id, now):
    row = conn.execute(sa.select(chat.connections).where(
        chat.connections.c.account_id == account_id,
        chat.connections.c.provider == SHADOW_PROVIDER).with_for_update()).mappings().first()
    if row and row["generation"] == record["generation"]:
        return row
    binding_id = row["id"] if row else uuid4()
    generation = record["generation"]
    nonce, ciphertext = encrypt(service._root(), account_id, binding_id,
        generation, SHADOW_PLACEHOLDER, SHADOW_PROVIDER)
    values = dict(generation=generation, nonce=nonce, ciphertext=ciphertext,
        enabled=True, verified_at=record["verified_at"], updated_at=now,
        last_operation_id=request_id, last_operation_hash="0" * 64,
        revision=row["revision"] + 1 if row else 1)
    if row:
        conn.execute(sa.update(chat.connections).where(
            chat.connections.c.id == binding_id).values(**values))
    else:
        conn.execute(sa.insert(chat.connections).values(
            id=binding_id, account_id=account_id, provider=SHADOW_PROVIDER,
            created_at=now, **values))
    return conn.execute(sa.select(chat.connections).where(
        chat.connections.c.id == binding_id)).mappings().one()


def admit_platform(service, conn, account_id, material, head, allowed):
    """Existing Chat admission transaction owns all authorization and persistence."""
    if not service.platform_demo or material.attachment_ids:
        raise ChatError(422, "model_not_allowed")
    public_model = material.model.removeprefix(PLATFORM_MODEL_PREFIX)
    model = next((item for item in allowed
                  if item.id == public_model and item.provider == "deepseek"), None)
    if not model:
        raise ChatError(422, "model_not_allowed")
    record = conn.execute(sa.select(platform.connections).where(
        platform.connections.c.provider == "deepseek").with_for_update()).mappings().first()
    if (not record or not record["enabled"] or record["verified_at"] is None
            or record["model"] != public_model):
        raise ChatError(409, "platform_model_unavailable")
    now = service.now()
    active = conn.execute(sa.select(sa.func.count()).select_from(chat.requests.join(
        chat.connections, chat.requests.c.connection_id == chat.connections.c.id)).where(
        chat.connections.c.provider == SHADOW_PROVIDER,
        chat.requests.c.state.in_(("pending", "streaming")),
        chat.requests.c.deadline_at > now)).scalar_one()
    if active >= record["concurrency_limit"]:
        raise ChatError(429, "platform_concurrency_limit")
    _daily_budget(conn, record, now)
    binding = _shadow_binding(service, conn, account_id, record, material.request_id, now)
    revision = f"platform-demo:v1:catalog-{head['revision']}:key-{record['generation']}"
    return binding, revision, False, []


def platform_key(service, conn, root, request_row, shadow):
    """Read central secret only at execution, never from an account connection."""
    if not service.platform_demo:
        raise ChatError(503, "platform_model_unavailable")
    record = conn.execute(sa.select(platform.connections).where(
        platform.connections.c.provider == "deepseek")).mappings().first()
    if (not record or not record["enabled"] or record["verified_at"] is None
            or record["generation"] != request_row["credential_generation"]
            or shadow["generation"] != record["generation"]):
        raise ChatError(503, "credential_unavailable")
    try:
        return decrypt(root, PLATFORM_NAMESPACE, PLATFORM_ID, record["generation"],
                       record["nonce"], record["ciphertext"], AAD_PROVIDER)
    except (InvalidTag, ValueError, UnicodeError):
        raise ChatError(503, "credential_unavailable") from None
