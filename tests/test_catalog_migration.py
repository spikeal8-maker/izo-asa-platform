"""Catalog forward migration seeds finite IDs and guards audit history."""
import base64
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import os
from pathlib import Path
import socket
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from izo.accounts import tables as a
from izo.accounts import repository as accounts_repo
from izo.accounts.security import hash_password
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.admin import tables as admin_tables
from izo.catalog import tables as c
from izo.catalog.schemas import CatalogPatch
from izo.catalog.service import CatalogError, CatalogService
from izo.chat import tables as chat_tables
from izo.chat.execution import FakeDeepSeekProvider
from izo.chat.schemas import ChatSettings, CredentialCommand, CredentialWrite, RequestCreate
from izo.chat.service import ChatError, ChatService


ORIGINAL_CONNECT = socket.socket.connect
ORIGINAL_CREATE_CONNECTION = socket.create_connection


PATH = Path(__file__).resolve().parents[1] / "apps/api/migrations/versions/0013_admin_catalog.py"
spec = importlib.util.spec_from_file_location("catalog_migration_0013", PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_migration_parent_and_no_runtime_schema_import():
    assert migration.revision == "0013_admin_catalog"
    assert migration.down_revision == "0012_chat"
    text = PATH.read_text()
    assert "izo.catalog" not in text and "create_all" not in text


def test_sqlite_upgrade_seed_immutable_audit_and_refused_downgrade():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        a.accounts.create(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        assert conn.execute(sa.text("SELECT revision, default_model FROM catalog_state")).one() == (1, "deepseek-flash")
        rows = conn.execute(sa.text("SELECT id, published, enabled FROM catalog_models ORDER BY id")).all()
        assert rows == [("deepseek-flash", 1, 1), ("deepseek-v4-pro", 1, 1),
                        ("fal.flux2.klein.4b", 0, 0)]
        actor = uuid4()
        conn.execute(sa.insert(a.accounts).values(id=actor, public_code=actor.hex[:16],
                     display_name="Catalog operator", state="active", created_at=1))
        conn.execute(sa.insert(c.events).values(operation_id=uuid4(), actor_id=actor,
            model_id="deepseek-flash", revision=2, fingerprint="a" * 64,
            reason="acceptance", before_json={}, after_json={}, created_at=2))
        with pytest.raises(sa.exc.DBAPIError):
            conn.execute(sa.text("UPDATE catalog_events SET reason='rewrite'"))
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match="populated catalog audit"):
                migration.downgrade()
    engine.dispose()


def test_empty_audit_allows_downgrade():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        a.accounts.create(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.downgrade()
        assert "catalog_state" not in sa.inspect(conn).get_table_names()
    engine.dispose()


def test_postgres_ddl_contains_price_bounds_and_append_only_guard():
    output = io.StringIO()
    context = MigrationContext.configure(dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        migration.upgrade()
    text = output.getvalue()
    assert "catalog_input_price_bound" in text
    assert "catalog_image_price_bound" in text
    assert "catalog_events_no_change" in text
    assert "catalog_events_no_truncate" in text


@pytest.mark.integration
def test_disposable_postgres_migration_cas_restart_and_chat_admission(monkeypatch):
    url = os.getenv("IZO_CATALOG_TEST_PG_URL")
    if not url:
        pytest.skip("IZO_CATALOG_TEST_PG_URL is required for isolated PostgreSQL acceptance")
    # The module-wide unit fixture forbids sockets. Restore them only for this
    # explicit, env-gated disposable-DB integration test.
    monkeypatch.setattr(socket.socket, "connect", ORIGINAL_CONNECT)
    monkeypatch.setattr(socket, "create_connection", ORIGINAL_CREATE_CONNECTION)
    schema = "catalog_it_" + uuid4().hex[:16]
    base = sa.create_engine(url)
    engine = None
    try:
        with base.begin() as conn:
            conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        options = {"options": f"-csearch_path={schema}"}
        engine = sa.create_engine(url, connect_args=options)
        with engine.begin() as conn:
            base_tables = (a.accounts, a.identities, a.passwords, a.sessions,
                           a.permissions, a.audit, admin_tables.events)
            a.metadata.create_all(conn, tables=base_tables)
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
            chat_tables.metadata.create_all(conn, tables=list(chat_tables.TABLES))
            assert conn.execute(sa.select(c.state.c.revision)).scalar_one() == 1
            assert set(conn.execute(sa.select(c.models.c.id)).scalars()) == {
                "deepseek-flash", "deepseek-v4-pro", "fal.flux2.klein.4b"}

        policy = AuthSettings(registration="invite", rate_secret="catalog-integration-rate-" * 3)
        auth = AuthService(engine, policy, clock=lambda: 20_000)
        owner, user = uuid4(), uuid4()
        sessions = []
        password_hash = hash_password("Synthetic-catalog-PG-only")
        with engine.begin() as conn:
            for account_id, name, email in ((owner, "Owner", "owner@example.invalid"),
                                            (user, "Chat user", "chat@example.invalid")):
                identity_id = uuid4()
                conn.execute(sa.insert(a.accounts).values(id=account_id,
                    public_code=account_id.hex[:16], display_name=name,
                    state="active", created_at=19_000))
                conn.execute(sa.insert(a.identities).values(id=identity_id,
                    account_id=account_id, provider="email", subject=email,
                    verified_at=19_000))
                conn.execute(sa.insert(a.passwords).values(
                    identity_id=identity_id, password_hash=password_hash))
                sessions.append(auth._new_session(conn,
                    accounts_repo.account_by_id(conn, account_id), "pg catalog", 20_000))
            for permission in ("catalog.read", "catalog.write", "pricing.write"):
                conn.execute(sa.insert(a.permissions).values(
                    account_id=owner, permission=permission))
        owner_session, chat_session = sessions
        catalog = CatalogService(auth)

        def patch(model_id, revision, *, enabled=True, is_default=False):
            return CatalogPatch(operation_id=uuid4(), expected_revision=revision,
                published=True, enabled=enabled, is_default=is_default,
                price={"currency": "RUB", "input_kopeks_per_million": None,
                       "output_kopeks_per_million": None, "image_kopeks_per_image": None},
                reason="isolated PostgreSQL catalog acceptance")

        race = Barrier(2)
        def change_default():
            race.wait(timeout=10)
            try:
                return ("ok", catalog.patch(owner_session.bearer,
                    owner_session.view.csrf_token, "deepseek-v4-pro",
                    patch("deepseek-v4-pro", 1, is_default=True)).revision)
            except CatalogError as error:
                return ("error", error.status, error.code)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(change_default)
            second = pool.submit(change_default)
            outcomes = [first.result(timeout=20), second.result(timeout=20)]
        assert sorted(outcomes) == [("error", 409, "catalog_revision_conflict"), ("ok", 2)]
        with engine.begin() as conn:
            assert conn.execute(sa.select(sa.func.count()).select_from(c.events)).scalar_one() == 1

        engine.dispose()
        engine = sa.create_engine(url, connect_args=options)
        auth = AuthService(engine, policy, clock=lambda: 20_000)
        catalog = CatalogService(auth)
        assert catalog.read(owner_session.bearer).revision == 2
        root_key = base64.urlsafe_b64encode(b"x" * 32).decode("ascii").rstrip("=")
        chat_policy = ChatSettings(root_key=root_key,
            preview_account_emails="chat@example.invalid")
        chat = ChatService(auth, chat_policy, FakeDeepSeekProvider(), clock=lambda: 20_000)
        saved = chat.save_credential(chat_session.bearer,
            chat_session.view.csrf_token,
            CredentialWrite(operation_id=uuid4(), key="x" * 32))
        chat.verify_credential(chat_session.bearer, chat_session.view.csrf_token,
            CredentialCommand(operation_id=uuid4(), expected_revision=saved.revision))
        thread = chat.create_thread(chat_session.bearer, chat_session.view.csrf_token, None)

        race = Barrier(2)
        request_id = uuid4()
        def admit():
            race.wait(timeout=10)
            try:
                return ("ok", chat.create_request(chat_session.bearer,
                    chat_session.view.csrf_token, thread.id,
                    RequestCreate(request_id=request_id, text="PG race",
                                  model="deepseek-flash")).id)
            except ChatError as error:
                return ("error", error.status, error.code)

        def disable():
            race.wait(timeout=10)
            return catalog.patch(owner_session.bearer,
                owner_session.view.csrf_token, "deepseek-flash",
                patch("deepseek-flash", 2, enabled=False)).revision

        with ThreadPoolExecutor(max_workers=2) as pool:
            admitted = pool.submit(admit)
            disabled = pool.submit(disable)
            outcome, revision = admitted.result(timeout=20), disabled.result(timeout=20)
        assert revision == 3
        if outcome[0] == "ok":
            with engine.begin() as conn:
                pinned = conn.execute(sa.select(chat_tables.requests.c.model_revision).where(
                    chat_tables.requests.c.id == request_id)).scalar_one()
                assert pinned.endswith("catalog-2")
        else:
            assert outcome == ("error", 422, "model_not_allowed")
        assert [m.id for m in chat.public_policy(chat_session.bearer).models] == ["deepseek-v4-pro"]
    finally:
        if engine is not None:
            engine.dispose()
        with base.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        base.dispose()
