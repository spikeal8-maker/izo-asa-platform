"""Isolated real-PostgreSQL absent-row quota race. Never runs in default CI."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import sqlalchemy as sa
from izo.chat.credential_crypto import encrypt
from izo.chat.schemas import ChatSettings
from izo.platform_providers.namespace import AAD_PROVIDER, PLATFORM_ID, PLATFORM_NAMESPACE

from izo.accounts.repository import create_auth_engine
from izo.chat.credentials import ChatError
from izo.chat.platform_admission import _daily_budget
from izo.config import Settings
from izo.platform_providers import tables as platform


def main():
    config = Settings()
    if (config.environment != "test"
            or config.pg_host != "postgres"
            or os.getenv("IZO_P0_PLATFORM_PG_ACCEPTANCE") != "isolated"):
        raise SystemExit("Explicit isolated PostgreSQL test environment required")
    engine = create_auth_engine(config)
    seeded_for_test = False
    with engine.begin() as conn:
        existing = conn.execute(sa.select(platform.connections).where(
            platform.connections.c.provider == "deepseek")).mappings().first()
        if existing is None:
            # Fresh disposable CI database: synthetic key only, no external requests.
            root = ChatSettings().root_key_bytes()
            nonce, ciphertext = encrypt(root, PLATFORM_NAMESPACE, PLATFORM_ID,
                                        1, "x" * 32, AAD_PROVIDER)
            conn.execute(sa.insert(platform.connections).values(
                provider="deepseek", generation=1, revision=1,
                nonce=nonce, ciphertext=ciphertext, enabled=True,
                verified_at=int(time.time()), model="deepseek-flash",
                daily_limit=3, concurrency_limit=1,
                last_operation_id=uuid4(), last_operation_hash="0" * 64,
                created_at=int(time.time()), updated_at=int(time.time())))
            seeded_for_test = True
    # Deliberately outside current UTC day; the test cannot consume user/demo quota.
    future_day = ((int(time.time()) // 86400) + 2000
                  + int(uuid4().hex[:3], 16)) * 86400
    gates = Barrier(6)
    outcomes = []

    def admitted(_):
        gates.wait(timeout=5)
        try:
            with engine.begin() as conn:
                # This is the SAME serialize-before-read sequence as admit_platform.
                record = conn.execute(sa.select(platform.connections).where(
                    platform.connections.c.provider == "deepseek")
                    .with_for_update()).mappings().one()
                policy = dict(record, daily_limit=3)
                _daily_budget(conn, policy, future_day + 42)
            return "admitted"
        except ChatError as error:
            return f"reject:{error.status}:{error.code}"

    try:
        with engine.begin() as conn:
            assert conn.dialect.name == "postgresql"
            assert conn.execute(sa.select(sa.func.count()).select_from(
                platform.daily_usage).where(
                platform.daily_usage.c.day_start == future_day)).scalar_one() == 0
        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(admitted, range(6)))
        assert outcomes.count("admitted") == 3, outcomes
        assert outcomes.count("reject:429:platform_daily_limit") == 3, outcomes
        with engine.begin() as conn:
            row = conn.execute(sa.select(platform.daily_usage).where(
                platform.daily_usage.c.provider == "deepseek",
                platform.daily_usage.c.day_start == future_day)).mappings().one()
            assert row["requests_admitted"] == 3
            assert row["confirmed_cost_microusd"] == 0
        print("P0_PLATFORM_PG_ABSENT_USAGE_RACE_PASS success=3 rejected=3")
        print("P0_PLATFORM_PG_CONFIRMED_COST_MICROUSD=0")
    finally:
        # Only the unique row created by this test; production/day data is untouched.
        with engine.begin() as conn:
            conn.execute(sa.delete(platform.daily_usage).where(
                platform.daily_usage.c.provider == "deepseek",
                platform.daily_usage.c.day_start == future_day))
            if seeded_for_test:
                conn.execute(sa.delete(platform.connections).where(
                    platform.connections.c.provider == "deepseek",
                    platform.connections.c.generation == 1))
        engine.dispose()


if __name__ == "__main__":
    main()
