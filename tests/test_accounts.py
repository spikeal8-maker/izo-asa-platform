"""Core Accounts identity test plus compatibility helper exports."""
import sqlalchemy as sa

from izo.accounts import tables as t
from izo.accounts.service import AuthService
from izo.accounts.security import token_hash, verify_password
from test_accounts_support import HEADERS, ORIGIN, PASSWORD, context, registration, signup


def test_account_is_persistent_server_identity_and_hashed_secrets(context):
    service, client, _ = context
    result = signup(service, client)
    data = result.json()
    assert data["account"]["permissions"] == []
    assert data["account"]["email_verified"] is False
    raw = client.cookies[service.policy.cookie_name]
    assert "HttpOnly" in result.headers["set-cookie"] and "SameSite=lax" in result.headers["set-cookie"]
    assert raw not in result.text and PASSWORD not in result.text
    with service.engine.begin() as conn:
        stored = conn.execute(sa.select(t.passwords.c.password_hash)).scalar_one()
        stored_token = conn.execute(sa.select(t.sessions.c.token_hash)).scalar_one()
        assert stored_token == token_hash(raw) and stored_token != raw
        assert stored != PASSWORD and verify_password(PASSWORD, stored)
    restarted = AuthService(service.engine, service.policy, service.clock)
    assert restarted.me(raw).account.id == service.me(raw).account.id
    assert client.get("/api/v1/auth/me").json()["account"]["id"] == data["account"]["id"]


__all__ = ["HEADERS", "ORIGIN", "PASSWORD", "context", "registration", "signup"]
