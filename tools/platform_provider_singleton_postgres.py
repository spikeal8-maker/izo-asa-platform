"""P0 singleton registry race: two authorized actors, real PostgreSQL, no paid calls."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import time
from uuid import uuid4
import sqlalchemy as sa

from izo.accounts import tables as accounts, repository
from izo.accounts.repository import create_auth_engine
from izo.accounts.security import AuthError, hash_password
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.admin import tables as audit
from izo.chat.execution import FakeDeepSeekProvider
from izo.chat.schemas import ChatSettings
from izo.config import Settings
from izo.platform_providers import tables as provider
from izo.platform_providers.schemas import ReplaceKey
from izo.platform_providers.service import PlatformProviderService


def main():
    config = Settings()
    if (config.environment != "test" or config.pg_host != "postgres" or
            os.getenv("IZO_P0_PLATFORM_PG_ACCEPTANCE") != "isolated"):
        raise SystemExit("Disposable isolated PostgreSQL test environment required")
    engine = create_auth_engine(config)
    now = int(time())
    auth = AuthService(engine, AuthSettings(
        registration="open", rate_secret="qa-platform-singleton-" * 3,
        login_limit=100, network_limit=1000), clock=lambda: now)
    service = PlatformProviderService(auth, FakeDeepSeekProvider(), ChatSettings())
    users, commands = [], []
    assert engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(
            provider.connections)).scalar_one() == 0
        hashed = hash_password("synthetic-password-singleton-qa")
        for idx in range(2):
            uid, iid = uuid4(), uuid4()
            conn.execute(sa.insert(accounts.accounts).values(
                id=uid, public_code=uid.hex[:16], state="active",
                display_name=f"Singleton QA {idx}", created_at=now - 10))
            conn.execute(sa.insert(accounts.identities).values(
                id=iid, account_id=uid, provider="email",
                subject=f"singleton-{uid.hex}@example.invalid", verified_at=now - 10))
            conn.execute(sa.insert(accounts.passwords).values(
                identity_id=iid, password_hash=hashed))
            for name in ("connections.read", "connections.write", "secrets.bind"):
                conn.execute(sa.insert(accounts.permissions).values(
                    account_id=uid, permission=name))
            receipt = auth._new_session(conn, repository.account_by_id(conn, uid),
                                        "P0 singleton QA", now)
            users.append((uid, receipt.bearer, receipt.view.csrf_token))
            commands.append(ReplaceKey(
                operation_id=uuid4(), expected_revision=None,
                key="x" * 32, current_password="synthetic-password-singleton-qa"))
    original = service._authorized
    barrier = Barrier(2)
    def align(conn, raw, csrf, permissions, proof):
        actor = original(conn, raw, csrf, permissions, proof)
        barrier.wait(timeout=15)  # after separate per-account locks, before singleton lock
        return actor
    service._authorized = align

    def submit(idx):
        _, bearer, csrf = users[idx]
        try:
            return ("success", idx, service.replace_key(
                bearer, csrf, commands[idx], f"qa-peer-{idx}").revision)
        except AuthError as exc:
            return ("rejected", idx, exc.status, exc.code)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, range(2)))
        assert sum(row[0] == "success" for row in results) == 1, results
        assert sum(row[0] == "rejected" and row[2:] == (409, "provider_revision_conflict")
                   for row in results) == 1, results
        service._authorized = original
        winner = next(row[1] for row in results if row[0] == "success")
        replay = service.replace_key(users[winner][1], users[winner][2],
                                     commands[winner], "qa-replay")
        assert replay.revision == 1
        with engine.begin() as conn:
            entry = conn.execute(sa.select(provider.connections)).mappings().one()
            assert entry["revision"] == 1 and entry["generation"] == 1
            rows = conn.execute(sa.select(audit.events.c.outcome).where(
                audit.events.c.action == "platform.key.replaced")).scalars().all()
            assert sorted(rows) == ["denied", "success"], rows
        print("P0_PLATFORM_REAL_PG_SINGLETON_INITIALIZATION_PASS success=1 conflict=1")
        print("P0_PLATFORM_REAL_PG_SINGLETON_UUID_REPLAY_PASS no_duplicate_success")
    finally:
        service._authorized = original
        with engine.begin() as conn:
            conn.execute(sa.delete(provider.connections).where(
                provider.connections.c.provider == "deepseek",
                provider.connections.c.generation == 1))
        # Admin audit is append-only by a PostgreSQL trigger; never delete it.
        # Synthetic actors/events live only in disposable CI Compose volumes,
        # removed by the owning workflow's down -v after both race checks.
        engine.dispose()


if __name__ == "__main__":
    main()
