"""Chat image HTTP and forward migration contracts."""
import hashlib
import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from izo.chat import tables as chat
from test_chat_http import http_env, save_and_verify, signup
from test_chat_vision import Objects


def test_image_only_http_roundtrip_and_safe_validation(http_env):
    _, service, client = http_env
    account = signup(None, client, "alice@example.invalid")
    save_and_verify(client)
    chat.media_assets.create(service.engine, checkfirst=True)
    objects = Objects()
    service.media_store = objects
    asset_id = uuid4()
    key = "test/" + str(asset_id)
    data = b"normalized-private-image"
    objects.values[key] = data
    with service.engine.begin() as conn:
        conn.execute(sa.insert(chat.media_assets).values(
            id=asset_id, account_id=UUID(account["account"]["id"]),
            object_key=key, sha256=hashlib.sha256(data).hexdigest(),
            byte_size=len(data), width=8, height=8, created_at=service.now()))
    thread = client.post("/api/v1/chat/threads", json={"title": None})
    assert thread.status_code == 201
    url = "/api/v1/chat/threads/" + thread.json()["id"]
    uid = str(uuid4())
    command = {"request_id": uid, "text": "", "model": "deepseek-flash",
               "attachment_ids": [str(asset_id)]}
    accepted = client.post(url + "/requests", json=command)
    assert accepted.status_code == 202, accepted.text
    assert client.post(url + "/requests", json=command).status_code == 202
    detail = client.get(url)
    assert detail.status_code == 200
    attachment = detail.json()["messages"][0]["attachments"][0]
    assert attachment["asset_id"] == str(asset_id)
    assert "object_key" not in detail.text and key not in detail.text
    assert client.post(url + "/requests", json={**command,
        "request_id": str(uuid4()), "attachment_ids": [str(asset_id), str(asset_id)]}
    ).json() == {"error": {"code": "invalid_input"}}


def test_forward_vision_migration_extends_multi_provider_schema():
    path = Path(__file__).resolve().parents[1] / (
        "apps/api/migrations/versions/0015_chat_vision.py")
    spec = importlib.util.spec_from_file_location("chat_vision_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "0014_chat_multi_provider"
    engine = sa.create_engine("sqlite://")
    meta = sa.MetaData()
    for name in ("accounts", "media_assets", "chat_requests", "chat_messages"):
        sa.Table(name, meta, sa.Column("id", sa.Uuid, primary_key=True))
    meta.create_all(engine)
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        inspector = sa.inspect(conn)
        columns = {column["name"] for column in inspector.get_columns("chat_requests")}
        assert "vision_admitted" in columns
        fks = inspector.get_foreign_keys("chat_message_attachments")
        assert {fk["referred_table"] for fk in fks} == {
            "accounts", "media_assets", "chat_requests", "chat_messages"}
