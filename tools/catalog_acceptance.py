"""CATALOG-001 real PostgreSQL/HTTP/race/restart acceptance. No provider network or raw secret.

Synthetic cookie/password state is redirected to RUNNER_TEMP with umask 077 by CI.
The credential reference is metadata only; no real OpenRouter key is used.
"""
import json
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from auth_acceptance import Client, check
from izo.accounts import repository as ar, tables as accounts
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.catalog import tables as t
from izo.catalog.schemas import (CapabilityDraft, ConnectionDraft, CredentialBind, DisableInput,
    ProofInput, PublishInput, RevokeCredential, CatalogError)
from izo.catalog.service import CatalogService
from izo.config import Settings

PERMISSIONS = ("catalog.read", "catalog.write", "connections.read", "connections.write",
               "secrets.bind", "pricing.write")
BASE = "http://api:8000/api/v1/admin/catalog"


def fixture(auth, label):
    password = secrets.token_urlsafe(28)
    client = Client(auth.policy.cookie_name)
    status, body = client.call("POST", "/register", {"email":"catalog-ci-"+uuid4().hex+"@example.invalid",
        "password":password, "display_name":"Catalog CI "+label, "invite_code":auth.issue_invite()})
    check(status == 201, "catalog_fixture_register")
    account_id = UUID(body["account"]["id"])
    with auth.engine.begin() as conn:
        conn.execute(sa.update(accounts.identities).where(accounts.identities.c.account_id == account_id)
                     .values(verified_at=auth.now()))
    return client, {"id":str(account_id), "password":password, "raw":client.raw, "csrf":client.csrf}


def http(client, method, path, data=None):
    headers = {"Cookie":client.name+"="+client.raw, "Origin":"http://localhost:8080",
               "X-IZO-Request":"web", "X-CSRF-Token":client.csrf,
               "Content-Type":"application/json"}
    request = Request(BASE+path, method=method, headers=headers,
        data=(json.dumps(data).encode() if data is not None else None))
    try:
        response = urlopen(request, timeout=20)
    except HTTPError as exc:
        response = exc
    with response:
        raw = response.read(131072)
        return response.status, json.loads(raw) if raw else None


def connection(operation=None, expected=0):
    return ConnectionDraft(operation_id=operation or uuid4(), expected_version=expected,
        reason="isolated catalog acceptance", account_ref="openrouter-ci-account",
        project_ref="images", environment="test", max_concurrency=2, rate_limit=20,
        rate_window_seconds=60, spend_cap_minor=0, currency="USD", timeout_seconds=180,
        allow_fallbacks=False)


def capability(operation=None, expected=0, name="OpenRouter CI image"):
    return CapabilityDraft(operation_id=operation or uuid4(), expected_version=expected,
        reason="isolated catalog acceptance", name=name, help="offline contract only",
        adapter_id="openrouter.images.v1", model_id="google/gemini-2.5-flash-image",
        connection_id="openrouter-primary", resolutions=("512",), price_credits=3)


def credential(password, operation=None, expected=1, version=1):
    ref = "IZO_OPENROUTER_API_KEY" if version == 1 else "vault/izo/openrouter/ci-v2"
    source = "env" if version == 1 else "secret_manager"
    return CredentialBind(operation_id=operation or uuid4(), expected_version=expected,
        reason="isolated credential metadata", source_type=source, secret_ref=ref,
        environment="test", account_ref="openrouter-ci-account", project_ref="images",
        current_password=password)


def race(functions):
    gate = Barrier(len(functions))
    def run(fn):
        gate.wait(timeout=10)
        try: return fn()
        except CatalogError as exc: return exc.code
    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(run, functions))


def immutable(engine):
    for sql in ("UPDATE catalog_capability_revisions SET revision=revision",
                "DELETE FROM catalog_connection_revisions",
                "UPDATE catalog_contract_proofs SET evidence_hash=evidence_hash",
                "DELETE FROM catalog_changes", "TRUNCATE catalog_changes"):
        try:
            with engine.begin() as conn: conn.execute(sa.text(sql))
        except DBAPIError as exc:
            check(getattr(exc.orig, "sqlstate", None) == "55000", "catalog_immutable_sqlstate")
        else:
            raise AssertionError("catalog_history_mutated")


def before(auth, service):
    a, actor_a = fixture(auth, "operator-a")
    b, actor_b = fixture(auth, "operator-b")
    ordinary, user = fixture(auth, "ordinary")
    with auth.engine.begin() as conn:
        for actor in (UUID(actor_a["id"]), UUID(actor_b["id"])):
            conn.execute(sa.insert(accounts.permissions), [
                {"account_id":actor, "permission":permission} for permission in PERMISSIONS])
    conn_operation = uuid4()
    first = connection(conn_operation)
    service.save_connection(a.raw, a.csrf, "openrouter-primary", first)
    service.bind_credential(a.raw, a.csrf, "openrouter-primary", credential(actor_a["password"]), "catalog-ci")
    service.save_capability(a.raw, a.csrf, "openrouter.image.v1", capability())

    commands = [capability(expected=1, name="Concurrent A"), capability(expected=1, name="Concurrent B")]
    results = race([lambda: service.save_capability(a.raw, a.csrf, "openrouter.image.v1", commands[0]),
                    lambda: service.save_capability(b.raw, b.csrf, "openrouter.image.v1", commands[1])])
    check(results.count("revision_conflict") == 1, "catalog_capability_version_race")
    winner = next(item for item in results if not isinstance(item, str))
    winner_cmd = commands[0] if winner.operation_id == commands[0].operation_id else commands[1]
    winner_client = a if winner.operation_id == commands[0].operation_id else b

    proof = service.proof(winner_client.raw, winner_client.csrf, "openrouter.image.v1",
        ProofInput(operation_id=uuid4(), expected_version=2, connection_id="openrouter-primary",
                   connection_version=2, reason="offline contract proof"))
    check(not proof.network_called and not proof.live_ready, "catalog_proof_must_be_offline")
    service.publish_connection(winner_client.raw, winner_client.csrf, "openrouter-primary",
        PublishInput(operation_id=uuid4(), expected_version=2, proof_id=proof.proof_id,
                     reason="publish disabled connection"))
    service.publish_capability(winner_client.raw, winner_client.csrf, "openrouter.image.v1",
        PublishInput(operation_id=uuid4(), expected_version=2, proof_id=proof.proof_id,
                     reason="publish capability metadata"))

    # A new draft can be proven, but rotating its credential makes that proof stale.
    service.save_capability(a.raw, a.csrf, "openrouter.image.v1", capability(expected=3, name="Next draft"))
    stale = service.proof(a.raw, a.csrf, "openrouter.image.v1",
        ProofInput(operation_id=uuid4(), expected_version=4, connection_id="openrouter-primary",
                   connection_version=3, reason="proof before rotation"))
    rotated = service.bind_credential(a.raw, a.csrf, "openrouter-primary",
        credential(actor_a["password"], expected=3, version=2), "catalog-ci")
    check(rotated.version == 2, "catalog_rotation_version")
    try:
        service.publish_capability(a.raw, a.csrf, "openrouter.image.v1",
            PublishInput(operation_id=uuid4(), expected_version=4, proof_id=stale.proof_id,
                         reason="must reject stale proof"))
    except CatalogError as exc:
        check(exc.code == "proof_stale", "catalog_rotation_stales_proof")
    else:
        raise AssertionError("catalog_stale_proof_published")
    current_proof = service.proof(a.raw, a.csrf, "openrouter.image.v1",
        ProofInput(operation_id=uuid4(), expected_version=4, connection_id="openrouter-primary",
                   connection_version=4, reason="proof after rotation"))
    service.revoke_credential(a.raw, a.csrf, "openrouter-primary",
        RevokeCredential(operation_id=uuid4(), expected_version=4, reason="isolated revoke",
                         current_password=actor_a["password"]), "catalog-ci")

    # Read surface is real HTTP and never exposes the opaque secret reference.
    status, model = http(a, "GET", "/models/openrouter.image.v1")
    check(status == 200 and model["published"] is not None and model["runtime_available"] is False,
          "catalog_model_http")
    status, conn_view = http(a, "GET", "/connections/openrouter-primary")
    check(status == 200 and conn_view["runtime_state"] == "disabled" and conn_view["credential"] is None,
          "catalog_connection_disabled")
    check(http(a, "GET", "/connections/openrouter-primary/credential")[0] == 404,
          "catalog_revoked_credential_hidden")
    check(http(ordinary, "GET", "/models")[0] == 403, "catalog_ordinary_denied")
    invalid = connection(expected=5).model_dump(mode="json") | {"endpoint":"https://evil.invalid"}
    status, body = http(a, "POST", "/connections/openrouter-primary/draft", invalid)
    check(status == 422 and "evil.invalid" not in json.dumps(body), "catalog_endpoint_injection_denied")
    immutable(auth.engine)
    with auth.engine.begin() as conn:
        cred_rows = conn.execute(sa.select(t.credential_bindings).where(
            t.credential_bindings.c.connection_id == "openrouter-primary").order_by(t.credential_bindings.c.version)).mappings().all()
        check(len(cred_rows) == 2 and all(row["revoked_at"] is not None for row in cred_rows), "catalog_rotation_revoke_rows")
        check(not any("secret" in key.lower() for key in model.keys()), "catalog_public_no_secret_field")
    print("CATALOG_BEFORE_OK: PG version race, offline proof, disabled publish, rotation stale-proof, revoke, immutable history, HTTP scope", file=sys.stderr)
    print(json.dumps({"schema":1, "actor":actor_a, "cookie_name":a.name, "connection_command":first.model_dump(mode="json"),
                      "published_model_hash":model["published"]["content_hash"],
                      "published_connection_hash":conn_view["published"]["content_hash"],
                      "proof":str(current_proof.proof_id), "winning_operation":str(winner_cmd.operation_id)}))


def after(auth, service):
    state = json.loads(sys.stdin.read(32768)); check(state["schema"] == 1, "catalog_fixture_schema")
    actor = state["actor"]
    client = Client(state["cookie_name"], actor["raw"]); client.csrf = actor["csrf"]
    status, model = http(client, "GET", "/models/openrouter.image.v1")
    status2, connection_view = http(client, "GET", "/connections/openrouter-primary")
    check(status == status2 == 200, "catalog_http_after_restart")
    check(model["published"]["content_hash"] == state["published_model_hash"], "catalog_model_persisted")
    check(connection_view["published"]["content_hash"] == state["published_connection_hash"], "catalog_connection_persisted")
    check(connection_view["runtime_state"] == "disabled", "catalog_never_activated")
    check(http(client, "GET", "/connections/openrouter-primary/credential")[0] == 404,
          "catalog_revocation_persisted")
    command = ConnectionDraft.model_validate(state["connection_command"])
    replay = service.save_connection(client.raw, client.csrf, "openrouter-primary", command)
    check(replay.operation_id == command.operation_id and replay.result_version == 1,
          "catalog_replay_survives_restart")
    with auth.engine.begin() as conn:
        check(conn.execute(sa.select(sa.func.count()).select_from(t.capability_revisions)).scalar_one() == 3,
              "catalog_capability_history_persisted")
        check(conn.execute(sa.select(sa.func.count()).select_from(t.proofs)).scalar_one() == 3,
              "catalog_proofs_persisted")
    print("CATALOG_AFTER_OK: published hashes/history/revocation and exact replay persisted across Compose restart")


def main():
    config = Settings()
    if (config.environment != "test" or config.pg_host != "postgres" or config.pg_database != "izo"
            or os.environ.get("IZO_CATALOG_ACCEPTANCE") != "isolated"):
        raise SystemExit("Refusing catalog acceptance outside isolated CI")
    engine = ar.create_auth_engine(config)
    try:
        auth = AuthService(engine, AuthSettings()); service = CatalogService(auth)
        if sys.argv[1:] == ["before"]: before(auth, service)
        elif sys.argv[1:] == ["after"]: after(auth, service)
        else: raise SystemExit("Expected before or after")
    except Exception as exc:
        print("CATALOG_ACCEPTANCE_FAILED: "+type(exc).__name__, file=sys.stderr)
        if isinstance(exc, AssertionError): print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        engine.dispose()


if __name__ == "__main__": main()
