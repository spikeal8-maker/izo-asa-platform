"""Disposable PostgreSQL/S3 image Chat acceptance with synthetic credentials."""
import base64
import json
import os
import sys
from uuid import UUID, uuid4

import sqlalchemy as sa

from izo.accounts import tables as accounts
from izo.accounts.repository import create_auth_engine
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.chat import tables as chat_tables
from izo.chat.execution import FakeDeepSeekProvider
from izo.chat.schemas import (
    ChatSettings, CredentialCommand, CredentialWrite, RequestCreate)
from izo.chat.service import ChatError, ChatService
from izo.config import Settings
from izo.media.objects import MediaStore
from izo.media.service import MediaService
from media_acceptance import command, fixture, pixels

SYNTHETIC_KEY = "x" * 32
ROOT_KEY = base64.urlsafe_b64encode(b"v" * 32).decode().rstrip("=")


def service(auth, store, emails):
    return ChatService(auth, ChatSettings(
        root_key=ROOT_KEY, preview_account_emails=",".join(emails)),
        FakeDeepSeekProvider(), media_store=store)


def email_for(auth, account_id):
    with auth.engine.begin() as conn:
        return conn.execute(sa.select(accounts.identities.c.subject).where(
            accounts.identities.c.account_id == UUID(account_id),
            accounts.identities.c.provider == "email")).scalar_one()


def credential(chat, user):
    saved = chat.save_credential(user["bearer"], user["csrf"],
        CredentialWrite(operation_id=uuid4(), key=SYNTHETIC_KEY))
    chat.verify_credential(user["bearer"], user["csrf"],
        CredentialCommand(operation_id=uuid4(), expected_revision=saved.revision))


def before(auth, store):
    data = pixels()
    owner, other, _ = fixture(auth, data)  # publishes an isolated Media entitlement
    emails = [email_for(auth, user["id"]) for user in (owner, other)]
    media = MediaService(auth, store)
    intent = command(data)
    pending = media.begin(owner["bearer"], owner["csrf"], intent)
    assert media.begin(owner["bearer"], owner["csrf"], intent) == pending
    ready = media.submit(owner["bearer"], owner["csrf"], pending.id, data)
    assert ready.status == "ready" and ready.asset_id is not None
    chat = service(auth, store, emails)
    credential(chat, owner)
    thread = chat.create_thread(owner["bearer"], owner["csrf"], None)
    accepted = chat.create_request(owner["bearer"], owner["csrf"], thread.id,
        RequestCreate(request_id=uuid4(), text="", model="deepseek-flash",
                      attachment_ids=[ready.asset_id]))
    assert "message.done" in "".join(chat.stream_events(owner["bearer"], accepted.id))
    detail = chat.thread_detail(owner["bearer"], thread.id)
    assert detail.messages[0].attachments[0].asset_id == ready.asset_id
    other_thread = chat.create_thread(other["bearer"], other["csrf"], None)
    try:
        chat.create_request(other["bearer"], other["csrf"], other_thread.id,
            RequestCreate(request_id=uuid4(), text="private?", model="deepseek-flash",
                          attachment_ids=[ready.asset_id]))
    except ChatError as exc:
        assert exc.status == 404 and exc.code == "attachment_not_found"
    else:
        raise AssertionError("Foreign image admitted")
    print("CHAT_VISION_BEFORE_OK", file=sys.stderr)
    print(json.dumps({"owner": owner, "emails": emails, "thread": str(thread.id),
                      "asset": str(ready.asset_id), "request": str(accepted.id)}))


def after(auth, store):
    state = json.load(sys.stdin)
    owner = state["owner"]
    chat = service(auth, store, state["emails"])
    detail = chat.thread_detail(owner["bearer"], UUID(state["thread"]))
    assert detail.messages[0].attachments[0].asset_id == UUID(state["asset"])
    followup = chat.create_request(owner["bearer"], owner["csrf"],
        UUID(state["thread"]), RequestCreate(request_id=uuid4(),
            text="Опиши изображение ещё раз", model="deepseek-flash"))
    with auth.engine.begin() as conn:
        row = conn.execute(sa.select(chat_tables.requests).where(
            chat_tables.requests.c.id == followup.id)).mappings().one()
    messages = chat._context_and_key(UUID(owner["id"]), row)[-1]
    assert any(isinstance(item["content"], list) for item in messages)
    assert "message.done" in "".join(chat.stream_events(owner["bearer"], followup.id))
    print("CHAT_VISION_AFTER_OK: durable private image survived API restart")


def main():
    if (os.environ.get("IZO_CHAT_VISION_ACCEPTANCE") != "isolated"
            or os.environ.get("IZO_ENVIRONMENT") != "test"):
        raise SystemExit("Only explicitly enabled disposable test infrastructure is allowed")
    if len(sys.argv) != 2 or sys.argv[1] not in {"before", "after"}:
        raise SystemExit("Use before or after")
    config = Settings()
    if config.pg_host != "postgres" or config.s3_endpoint != "http://storage:8333":
        raise SystemExit("Only standard isolated Compose dependencies are allowed")
    engine = create_auth_engine(config)
    try:
        auth = AuthService(engine, AuthSettings())
        store = MediaStore(config)
        before(auth, store) if sys.argv[1] == "before" else after(auth, store)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
