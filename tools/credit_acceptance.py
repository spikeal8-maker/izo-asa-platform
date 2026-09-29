"""CREDIT-001 real PostgreSQL/HTTP/races and Compose restart. Isolated CI ONLY.

Synthetic rows remain in the disposable stack because ledger deletion is forbidden.
Fixture stdout MUST be redirected to a private RUNNER_TEMP file, never an artifact.
"""
import http.client
import json
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from auth_acceptance import Client, check
from izo.config import Settings
from izo.accounts import repository as auth_repo, tables as accounts
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.credits.schemas import CreditError, Grant, Reserve, Settle, Release
from izo.credits.service import CreditService
from izo.credits import tables as credits


def http_read(cookie_name, raw, query=""):
    connection = http.client.HTTPConnection("api", 8000, timeout=15)
    headers = {"Cookie": cookie_name + "=" + raw} if raw else {}
    try:
        connection.request("GET", "/api/v1/credits" + query, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read(65536))
    finally:
        connection.close()


def race(engine, functions):
    gate = Barrier(len(functions))
    def execute(fn):
        gate.wait(timeout=10)
        try:
            with engine.begin() as conn:
                return fn(conn)
        except CreditError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(execute, functions))


def immutability(engine, owner):
    commands = [
        "UPDATE credit_ledger SET reason=reason WHERE account_id=:owner",
        "DELETE FROM credit_ledger WHERE account_id=:owner",
        "TRUNCATE credit_ledger",
    ]
    for command in commands:
        try:
            with engine.begin() as conn:
                conn.execute(sa.text(command), {"owner": owner})
        except IntegrityError as exc:
            check(getattr(exc.orig, "sqlstate", None) == "23514", "ledger_trigger_sqlstate")
            check(getattr(getattr(exc.orig, "diag", None), "message_primary", "") ==
                  "credit_ledger_is_immutable", "ledger_trigger_message")
        else:
            raise AssertionError("immutable_ledger_operation_was_allowed")


def before(auth, service):
    clients, ids = [], []
    for role in ["owner", "other", "operator"]:
        client = Client(auth.policy.cookie_name)
        status, result = client.call("POST", "/register", {
            "email": "credit-ci-" + uuid4().hex + "@example.invalid",
            "password": secrets.token_urlsafe(32), "display_name": "Credit CI " + role,
            "invite_code": auth.issue_invite(),
        })
        check(status == 201, "credit_fixture_register")
        clients.append(client)
        ids.append(UUID(result["account"]["id"]))
    owner, other, staff = ids
    with auth.engine.begin() as conn:
        # Explicit synthetic test grants, never a public role/verification bypass.
        conn.execute(sa.update(accounts.identities).where(accounts.identities.c.account_id.in_(ids))
                     .values(verified_at=auth.now()))
        conn.execute(sa.insert(accounts.permissions).values(account_id=staff, permission="credits.grant"))
    command = Grant(operation_id=uuid4(), case_id=uuid4(), amount=100, reason="test_grant")
    results = race(auth.engine, [lambda conn: service.grant(conn, owner, staff, command, grant_limit=100)] * 2)
    check(results[0] == results[1] and not isinstance(results[0], str), "grant_race_idempotent")
    holds = [Reserve(operation_id=uuid4(), reservation_id=uuid4(), request_id=uuid4(), amount=70) for _ in range(2)]
    results = race(auth.engine, [lambda conn, cmd=cmd: service.reserve(conn, owner, cmd) for cmd in holds])
    check(sum(value == "insufficient_credits" for value in results) == 1, "no_parallel_overspend")
    successful = next(value for value in results if not isinstance(value, str))
    settle = Settle(operation_id=uuid4(), reservation_id=successful.reservation_id, amount=50)
    results = race(auth.engine, [lambda conn: service.settle(conn, owner, settle)] * 2)
    check(results[0] == results[1] and not isinstance(results[0], str), "settle_race_idempotent")
    with auth.engine.begin() as conn:
        try:
            service.grant(conn, other, staff, command.model_copy(update={"operation_id":uuid4()}), grant_limit=100)
        except CreditError as exc:
            check(exc.code == "source_already_used", "duplicate_case_is_rejected")
        else:
            raise AssertionError("duplicate_case_created_credits")
        service.grant(conn, owner, staff, Grant(operation_id=uuid4(), case_id=uuid4(), amount=50,
                                              reason="test_grant"), grant_limit=100)
        pending = Reserve(operation_id=uuid4(), reservation_id=uuid4(), request_id=uuid4(), amount=40)
        service.reserve(conn, owner, pending)
        temporary = Reserve(operation_id=uuid4(), reservation_id=uuid4(), request_id=uuid4(), amount=20)
        service.reserve(conn, owner, temporary)
    release = Release(operation_id=uuid4(), reservation_id=temporary.reservation_id)
    results = race(auth.engine, [lambda conn: service.release(conn, owner, release)] * 2)
    check(results[0] == results[1] and not isinstance(results[0], str), "release_race_idempotent")
    immutability(auth.engine, owner)
    with auth.engine.begin() as conn:
        check(service.reconcile(conn, owner).consistent, "ledger_projection_and_holds_match")
    status, view = http_read(clients[0].name, clients[0].raw)
    check(status == 200 and view["balance"] == {"balance":100,"reserved":40,"available":60,"sequence":7},
          "real_credits_http")
    status, blank = http_read(clients[1].name, clients[1].raw)
    check(status == 200 and blank["balance"]["available"] == 0 and not blank["entries"], "other_account_isolated")
    check(http_read(clients[0].name, "")[0] == 401, "anonymous_denied")
    check(http_read(clients[0].name, clients[0].raw, "?account_id="+str(other))[0] == 422, "client_owner_rejected")
    print("CREDIT_BEFORE_OK: PG races, one grant/case, no overspend, immutable journal and owner HTTP", file=sys.stderr)
    print(json.dumps({"schema":1,"owner":str(owner),"cookie_name":clients[0].name,
                      "cookie":clients[0].raw,"pending":pending.model_dump(mode="json")}))


def after(auth, service):
    item=json.loads(sys.stdin.read(8192))
    check(item["schema"] == 1, "credit_fixture_schema")
    owner = UUID(item["owner"])
    # Verify ownership through the existing Account API before using the fixture.
    client=Client(item["cookie_name"], item["cookie"])
    status, account=client.call("GET", "/me")
    check(status == 200 and account["account"]["id"] == str(owner) and
          account["account"]["email"].startswith("credit-ci-") and
          account["account"]["email"].endswith("@example.invalid"), "credit_fixture_identity")
    status, view=http_read(item["cookie_name"], item["cookie"])
    check(status == 200 and view["balance"] == {"balance":100,"reserved":40,"available":60,"sequence":7},
          "credits_survive_real_restart")
    pending=Reserve.model_validate(item["pending"])
    with auth.engine.begin() as conn:
        receipt=service.reserve(conn, owner, pending)
        check(receipt.sequence == 5, "retry_after_restart_returns_original_receipt")
        command=Release(operation_id=uuid4(), reservation_id=pending.reservation_id)
        receipt=service.release(conn, owner, command)
        check(service.release(conn, owner, command) == receipt, "pending_release_single_effect")
        check(service.reconcile(conn, owner).consistent, "reconcile_after_restart")
    status, view=http_read(item["cookie_name"], item["cookie"])
    check(status == 200 and view["balance"] == {"balance":100,"reserved":0,"available":100,"sequence":8},
          "release_after_restart")
    print("CREDIT_AFTER_OK: balance/ledger/hold persisted; retry unchanged; pending release works")
    # Do not disable immutability or delete financial rows. Final CI destroys only
    # the explicitly isolated test volumes; production cleanup is another policy.


def main():
    config=Settings()
    if (config.environment != "test" or config.pg_host != "postgres" or config.pg_database != "izo"
            or os.environ.get("IZO_CREDIT_ACCEPTANCE") != "isolated"):
        raise SystemExit("Refusing credit acceptance outside explicitly isolated CI")
    engine=auth_repo.create_auth_engine(config)
    try:
        auth=AuthService(engine, AuthSettings())
        service=CreditService()
        phase=sys.argv[1] if len(sys.argv)==2 else ""
        if phase == "before":
            before(auth, service)
        elif phase == "after":
            after(auth, service)
        else:
            raise ValueError("Expected before or after")
    except Exception as exc:
        print("CREDIT_ACCEPTANCE_FAILED: " + type(exc).__name__, file=sys.stderr)
        if isinstance(exc, AssertionError):
            print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
