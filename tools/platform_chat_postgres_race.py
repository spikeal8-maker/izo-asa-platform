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



def real_http_admission(engine):
    """Two distinct users hit real FastAPI/Graph admission simultaneously on PG."""
    import json
    from threading import Thread
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from izo.app import create_app
    from izo.accounts.service import AuthService
    from izo.accounts.settings import AuthSettings
    from izo.chat.execution import FakeDeepSeekProvider
    from izo.chat.service import ChatService
    from izo.chat import graph_requests, tables as chat
    import uvicorn

    suffix = uuid4().hex[:10]
    emails = [f"p0a-{suffix}@example.invalid", f"p0b-{suffix}@example.invalid"]
    auth = AuthService(engine, AuthSettings(
        registration="open", rate_secret="p0-real-pg-http-" * 4,
        login_limit=100, network_limit=1000))
    runtime = ChatService(auth, ChatSettings(preview_account_emails=",".join(emails)),
                          FakeDeepSeekProvider(), platform_demo=True)
    app = create_app(Settings(environment="test"), readiness=lambda: True)
    app.state.accounts_service = auth
    app.state.chat_service = runtime
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=8080, log_level="error",
        access_log=False, lifespan="off"))
    serving = Thread(target=server.run, daemon=True)
    serving.start()

    def http(path, method="GET", payload=None, session=None):
        headers = {"Origin": "http://localhost:8080", "X-IZO-Request": "web"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if session:
            headers["Cookie"], headers["X-CSRF-Token"] = session
        req = Request("http://localhost:8080" + path,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers=headers, method=method)
        try:
            response = urlopen(req, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            status = response.status
            body = response.read().decode()
            headers_out = response.headers
        return status, body, headers_out

    original = graph_requests.admit_platform
    try:
        for _ in range(100):
            try:
                if http("/api/health/live")[0] == 200:
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError("isolated loopback API never started")
        accounts = []
        for idx, email in enumerate(emails):
            code, body, headers = http("/api/v1/auth/register", "POST", {
                "email": email, "password": "synthetic-chat-http-password",
                "display_name": f"qa-{idx}"})
            assert code == 201, (code, body)
            details = json.loads(body)
            cookie = headers["Set-Cookie"].split(";", 1)[0]
            session = (cookie, details["csrf_token"])
            code, body, _ = http("/api/v1/chat/threads", "POST", {"title": None}, session)
            assert code == 201, (code, body)
            accounts.append((details["account"]["id"], session, json.loads(body)["id"]))
        assert accounts[0][0] != accounts[1][0]

        # Both requests must reach the *real* production admission function
        # before either can acquire the platform singleton row lock.
        admit_gate = Barrier(2)
        def synchronized_admission(*args, **kwargs):
            admit_gate.wait(timeout=15)
            return original(*args, **kwargs)
        graph_requests.admit_platform = synchronized_admission
        commands = [{"request_id": str(uuid4()), "text": f"Race {idx}",
                     "model": "platform:deepseek-flash"} for idx in range(2)]
        def send(idx):
            account, session, tid = accounts[idx]
            return http(f"/api/v1/chat/threads/{tid}/requests",
                        "POST", commands[idx], session)[:2]
        with ThreadPoolExecutor(max_workers=2) as pool:
            answers = list(pool.map(send, range(2)))
        graph_requests.admit_platform = original
        assert sorted(x[0] for x in answers) == [202, 429], answers
        winner = next(i for i, x in enumerate(answers) if x[0] == 202)
        loser = 1 - winner
        assert json.loads(answers[loser][1])["error"]["code"] == "platform_concurrency_limit"
        with engine.begin() as conn:
            start = runtime.now() // 86400 * 86400
            usage = conn.execute(sa.select(platform.daily_usage).where(
                platform.daily_usage.c.day_start == start)).mappings().one()
            assert usage["requests_admitted"] == 1
            assert usage["confirmed_cost_microusd"] == 0
            active = conn.execute(sa.select(chat.requests).where(
                chat.requests.c.state.in_(("pending", "streaming")))).mappings().all()
            assert len(active) == 1
            assert active[0]["account_id"] == __import__("uuid").UUID(accounts[winner][0])
        _, winner_session, winner_tid = accounts[winner]
        code, body, _ = http(f"/api/v1/chat/threads/{winner_tid}/requests",
                             "POST", commands[winner], winner_session)
        assert code == 202 and json.loads(body)["id"] == commands[winner]["request_id"]
        with engine.begin() as conn:
            assert conn.execute(sa.select(platform.daily_usage.c.requests_admitted).where(
                platform.daily_usage.c.day_start == start)).scalar_one() == 1
        code, stream, _ = http(f"/api/v1/chat/requests/{commands[winner]['request_id']}/events",
                               session=winner_session)
        assert code == 200 and "event: message.done" in stream, (code, stream[:350])
        _, loser_session, loser_tid = accounts[loser]
        code, body, _ = http(f"/api/v1/chat/threads/{loser_tid}/requests",
                             "POST", commands[loser], loser_session)
        assert code == 202, (code, body)
        with engine.begin() as conn:
            assert conn.execute(sa.select(platform.daily_usage.c.requests_admitted).where(
                platform.daily_usage.c.day_start == start)).scalar_one() == 2
        code, _, _ = http(f"/api/v1/chat/threads/{winner_tid}", session=loser_session)
        assert code == 404, code
        print("P0_PLATFORM_REAL_HTTP_PG_ADMISSION_RACE_PASS accepted=1 rejected=1", flush=True)
        print("P0_PLATFORM_REAL_HTTP_PG_EXACT_REPLAY_AND_RELEASE_PASS", flush=True)
    finally:
        graph_requests.admit_platform = original
        server.should_exit = True
        serving.join(timeout=10)


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
        real_http_admission(engine)
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
