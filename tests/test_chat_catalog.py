"""Catalog publication and price are server owned at Chat policy/admission."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.catalog import tables as catalog
from izo.chat import tables as chat
from izo.chat.schemas import RequestCreate
from izo.chat.schemas import MODEL_REVISION
from izo.chat.service import ChatError
from test_chat import chat_env, connect_key


def test_price_null_zero_and_disabled_model_admission(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    policy = service.public_policy(alice.bearer)
    assert policy.default_model == "deepseek-flash"
    assert [m.id for m in policy.models] == ["deepseek-flash", "deepseek-v4-pro"]
    assert policy.models[0].price.input_kopeks_per_million is None
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    command = RequestCreate(request_id=uuid4(), text="hello", model="deepseek-v4-pro")
    accepted = service.create_request(alice.bearer, alice.view.csrf_token, thread.id, command)
    with service.engine.begin() as conn:
        conn.execute(sa.update(catalog.state).where(catalog.state.c.id == 1).values(revision=2))
        conn.execute(sa.update(catalog.models).where(catalog.models.c.id == "deepseek-v4-pro")
                     .values(enabled=False))
        conn.execute(sa.update(catalog.models).where(catalog.models.c.id == "deepseek-flash")
                     .values(input_kopeks_per_million=0, output_kopeks_per_million=199))
    refreshed = service.public_policy(alice.bearer)
    assert [m.id for m in refreshed.models] == ["deepseek-flash"]
    assert refreshed.models[0].price.input_kopeks_per_million == 0
    assert refreshed.models[0].price.output_kopeks_per_million == 199
    with pytest.raises(ChatError, match="model_not_allowed"):
        service.create_request(alice.bearer, alice.view.csrf_token, thread.id,
            RequestCreate(request_id=uuid4(), text="new", model="deepseek-v4-pro"))
    assert service.create_request(alice.bearer, alice.view.csrf_token,
                                  thread.id, command) == accepted
    with service.engine.begin() as conn:
        revision = conn.execute(sa.select(chat.requests.c.model_revision).where(
            chat.requests.c.id == accepted.id)).scalar_one()
        assert "catalog-1" in revision


def test_legacy_fingerprint_replay_uses_stored_model_revision(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    command = RequestCreate(request_id=uuid4(), text="legacy", model="deepseek-v4-pro")
    accepted = service.create_request(alice.bearer, alice.view.csrf_token, thread.id, command)
    with service.engine.begin() as conn:
        row = conn.execute(sa.select(chat.requests).where(chat.requests.c.id == accepted.id)).mappings().one()
        old_hash = service._request_fingerprint(thread.id, command.text, command.model,
            row["connection_id"], row["credential_generation"], MODEL_REVISION)
        conn.execute(sa.update(chat.requests).where(chat.requests.c.id == accepted.id).values(
            model_revision=MODEL_REVISION, fingerprint=old_hash))
        conn.execute(sa.update(catalog.models).where(catalog.models.c.id == command.model)
                     .values(enabled=False))
    assert service.create_request(alice.bearer, alice.view.csrf_token, thread.id, command) == accepted
