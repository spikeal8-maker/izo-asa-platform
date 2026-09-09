"""Read-only, bounded probes. Never run migrations or contact AI providers here."""
from functools import lru_cache
from pathlib import Path

from .config import Settings
from .storage import S3Store


@lru_cache(maxsize=1)
def expected_schema_revision() -> str:
    """Read trusted packaged migration metadata, never connect or run upgrades.

    One immutable release has one merged Alembic head. Old/new/ambiguous database
    revisions are not accepted merely because some version row exists.
    """
    from alembic.script import ScriptDirectory
    migration_dir = Path(__file__).resolve().parents[1] / "migrations"
    heads = ScriptDirectory(str(migration_dir)).get_heads()
    if len(heads) != 1:
        raise ValueError("Expected exactly one packaged schema revision")
    return heads[0]


def database_ready(config: Settings) -> bool:
    if not config.pg_password.get_secret_value():
        return False
    try:
        expected = expected_schema_revision()
        import psycopg
        with psycopg.connect(host=config.pg_host, port=config.pg_port,
                             dbname=config.pg_database, user=config.pg_user,
                             password=config.pg_password.get_secret_value(),
                             connect_timeout=3,
                             options="-c statement_timeout=2000 -c default_transaction_read_only=on") as conn:
            rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
            return rows == [(expected,)]
    except Exception:
        return False


def dependencies_ready(config: Settings) -> bool:
    if not database_ready(config):
        return False
    if not config.s3_access_key.get_secret_value() or not config.s3_secret_key.get_secret_value():
        return False
    try:
        return S3Store(config).healthy()
    except Exception:
        return False
