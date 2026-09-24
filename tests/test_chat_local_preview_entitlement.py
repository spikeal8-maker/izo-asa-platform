"""Bounded dev-only entitlement for the local Chat preview account."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.accounts import tables as accounts
from izo.entitlements import tables as entitlements
from izo.entitlements.local_preview import (
    LOCAL_PREVIEW_MEDIA_REVISION_ID,
    ensure_local_preview_media,
)
from izo.entitlements.schemas import EntitlementError
from izo.entitlements.service import EntitlementService


@pytest.fixture
def preview_db():
    engine = sa.create_engine("sqlite://")
    tables = [
        accounts.accounts, accounts.identities, accounts.permissions,
        entitlements.revisions, entitlements.defaults, entitlements.assignments,
    ]
    accounts.metadata.create_all(engine, tables=tables)
    account_id = uuid4()
    with engine.begin() as conn:
        conn.execute(accounts.accounts.insert().values(
            id=account_id, public_code=uuid4().hex[:16],
            display_name="Local Preview", state="active", created_at=100))
        conn.execute(accounts.identities.insert().values(
            id=uuid4(), account_id=account_id, provider="email",
            subject="preview@local.izo", verified_at=100))
        conn.execute(entitlements.defaults.insert().values(
            id=1, revision_id=None, version=0))
    yield engine, account_id
    engine.dispose()


def test_dev_preview_entitlement_is_bounded_and_idempotent(preview_db):
    engine, account_id = preview_db
    with engine.begin() as conn:
        assert ensure_local_preview_media(
            conn, account_id, environment="development",
            local_preview_enabled=True, now=200)
    with engine.begin() as conn:
        assert ensure_local_preview_media(
            conn, account_id, environment="development",
            local_preview_enabled=True, now=300)
        view = EntitlementService(clock=lambda: 300).resolve(conn, account_id)
        assert view.configured and view.source == "assignment"
        assert view.revision_id == LOCAL_PREVIEW_MEDIA_REVISION_ID
        assert view.policy is not None
        assert view.policy.input_count == 5
        assert view.policy.upload_bytes == 12 * 1024 * 1024
        assert view.policy.storage_bytes == 256 * 1024 * 1024
        assert conn.scalar(sa.select(sa.func.count()).select_from(
            entitlements.revisions)) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(
            entitlements.assignments)) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(
            accounts.permissions)) == 0


@pytest.mark.parametrize(("environment", "enabled"), [
    ("production", True),
    ("development", False),
    ("test", True),
])
def test_dev_preview_entitlement_fails_closed_outside_explicit_dev(
        preview_db, environment, enabled):
    engine, account_id = preview_db
    with engine.begin() as conn:
        assert not ensure_local_preview_media(
            conn, account_id, environment=environment,
            local_preview_enabled=enabled, now=200)
        assert conn.scalar(sa.select(sa.func.count()).select_from(
            entitlements.revisions)) == 0
        assert conn.scalar(sa.select(sa.func.count()).select_from(
            entitlements.assignments)) == 0


def test_dev_preview_entitlement_conflict_is_not_overwritten(preview_db):
    engine, account_id = preview_db
    with engine.begin() as conn:
        conn.execute(entitlements.assignments.insert().values(
            account_id=account_id, revision_id=None,
            starts_at=None, expires_at=None, version=1))
    with pytest.raises(EntitlementError, match="local_preview_entitlement_conflict"):
        with engine.begin() as conn:
            ensure_local_preview_media(
                conn, account_id, environment="development",
                local_preview_enabled=True, now=200)
    with engine.begin() as conn:
        row = conn.execute(sa.select(entitlements.assignments).where(
            entitlements.assignments.c.account_id == account_id
        )).mappings().one()
        assert row["revision_id"] is None and row["version"] == 1
