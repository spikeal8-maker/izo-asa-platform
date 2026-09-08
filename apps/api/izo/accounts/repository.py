"""Bounded SQL access. PostgreSQL runtime; SQLite is used only by isolated unit tests."""
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.engine import Engine, URL

from . import tables as t


def create_auth_engine(config) -> Engine:
    url = URL.create("postgresql+psycopg", username=config.pg_user,
        password=config.pg_password.get_secret_value(), host=config.pg_host,
        port=config.pg_port, database=config.pg_database)
    return sa.create_engine(url, pool_size=5, max_overflow=2, pool_timeout=3,
        pool_pre_ping=True, hide_parameters=True, connect_args={"connect_timeout": 3,
        "options": "-c statement_timeout=5000 -c lock_timeout=3000"})


def account_query():
    return sa.select(t.accounts, t.identities.c.subject.label("email"),
        t.identities.c.verified_at, t.passwords.c.password_hash).outerjoin(
        t.identities, sa.and_(t.identities.c.account_id == t.accounts.c.id,
                              t.identities.c.provider == "email")).outerjoin(
        t.passwords, t.passwords.c.identity_id == t.identities.c.id)


def account_by_email(conn, email: str):
    return conn.execute(account_query().where(t.identities.c.subject == email)).mappings().first()


def account_by_id(conn, account_id, lock=False):
    query = account_query().where(t.accounts.c.id == account_id)
    if lock:
        query = query.with_for_update(of=t.accounts)
    return conn.execute(query).mappings().first()


def grant_names(conn, account_id, now: int) -> list[str]:
    return list(conn.execute(sa.select(t.permissions.c.permission).where(
        t.permissions.c.account_id == account_id,
        sa.or_(t.permissions.c.expires_at.is_(None), t.permissions.c.expires_at > now)
    ).order_by(t.permissions.c.permission)).scalars())


def event(conn, account_id, action: str, now: int, target_id=None) -> None:
    conn.execute(sa.insert(t.audit).values(id=uuid4(), account_id=account_id,
        action=action, target_id=target_id, created_at=now))


def consume_rate(conn, key: str, start: int, maximum: int) -> int:
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif conn.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError("Unsupported authentication database")
    query = insert(t.limits).values(bucket_key=key, window_start=start, count=1)
    query = query.on_conflict_do_update(
        index_elements=[t.limits.c.bucket_key, t.limits.c.window_start],
        set_={"count": sa.case((t.limits.c.count <= maximum, t.limits.c.count + 1),
                               else_=t.limits.c.count)}).returning(t.limits.c.count)
    return conn.execute(query).scalar_one()
