"""Catalog HTTP enforces staff grants, same-origin and strict body semantics."""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from izo.accounts.http_security import AuthBodyLimit
from izo.accounts.security import AuthError
from izo.catalog.routes import attach_catalog
from test_catalog import catalog_env


@pytest.fixture
def catalog_http(catalog_env):
    service, sessions, _ = catalog_env
    app = FastAPI()
    @app.exception_handler(AuthError)
    async def auth_error(request, error):
        return JSONResponse({"error": {"code": error.code}}, status_code=error.status)
    @app.exception_handler(RequestValidationError)
    async def input_error(request, error):
        return JSONResponse({"error": {"code": "invalid_input"}}, status_code=422)
    attach_catalog(app, lambda request: service.auth)
    app.add_middleware(AuthBodyLimit)
    with TestClient(app) as client:
        yield client, service, sessions


def headers(env, who=0):
    _, service, sessions = env
    return {"Cookie": service.auth.policy.cookie_name + "=" + sessions[who].bearer,
            "Origin": "http://localhost:8080", "X-IZO-Request": "web",
            "X-CSRF-Token": sessions[who].view.csrf_token}


def payload(**changes):
    data = {"operation_id": str(uuid4()), "expected_revision": 1,
            "published": True, "enabled": True, "is_default": False,
            "price": {"currency": "RUB", "input_kopeks_per_million": None,
                      "output_kopeks_per_million": None, "image_kopeks_per_image": None},
            "reason": "HTTP catalog acceptance"}
    data.update(changes)
    return data


PATH = "/api/v1/admin/catalog/models/deepseek-v4-pro"


def test_catalog_only_staff_reads_without_admin_me(catalog_http):
    client = catalog_http[0]
    assert client.get("/api/v1/admin/catalog", headers=headers(catalog_http, 2)).status_code == 200
    assert client.get("/api/v1/admin/catalog", headers=headers(catalog_http, 3)).status_code == 403
    assert client.get("/api/v1/admin/catalog").status_code == 401


def test_mutation_is_csrf_checked_and_price_needs_separate_grant(catalog_http):
    client = catalog_http[0]
    assert client.patch(PATH, headers=headers(catalog_http, 2), json=payload()).status_code == 403
    assert client.patch(PATH, headers={**headers(catalog_http, 0), "Origin": "https://else.invalid"},
                        json=payload()).status_code == 403
    priced = payload(price={"currency": "RUB", "input_kopeks_per_million": 0,
                            "output_kopeks_per_million": 100, "image_kopeks_per_image": None})
    assert client.patch(PATH, headers=headers(catalog_http, 1), json=priced).status_code == 403
    accepted = client.patch(PATH, headers=headers(catalog_http), json=priced)
    assert accepted.status_code == 200
    assert accepted.json()["revision"] == 2
    assert next(m for m in accepted.json()["models"] if m["id"] == "deepseek-v4-pro")["price"]["input_kopeks_per_million"] == 0
    assert client.patch(PATH, headers=headers(catalog_http), json=priced).json()["revision"] == 2


@pytest.mark.parametrize("bad", [
    {"actor_id": "forged"}, {"price": {"currency": "USD"}},
    {"price": {"currency": "RUB", "input_kopeks_per_million": -1}},
    {"price": {"currency": "RUB", "input_kopeks_per_million": 1.5}},
    {"enabled": "true"},
])
def test_unknown_or_malformed_values_rejected(catalog_http, bad):
    body = payload(**bad)
    response = catalog_http[0].patch(PATH, headers=headers(catalog_http), json=body)
    assert response.status_code == 422
    assert "HTTP catalog acceptance" not in response.text


def test_unapproved_id_and_stale_revision(catalog_http):
    client = catalog_http[0]
    assert client.patch("/api/v1/admin/catalog/models/openrouter-unknown",
                        headers=headers(catalog_http), json=payload()).json() == {
                            "error": {"code": "model_not_allowed"}}
    assert client.patch(PATH, headers=headers(catalog_http), json=payload()).status_code == 200
    stale = client.patch(PATH, headers=headers(catalog_http), json=payload())
    assert stale.status_code == 409
    assert stale.json() == {"error": {"code": "catalog_revision_conflict"}}
