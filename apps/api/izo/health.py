"""Read-only, bounded probes. Never run migrations or contact AI providers here."""
from .config import Settings
from .storage import S3Store


def database_ready(config: Settings) -> bool:
    if not config.pg_password.get_secret_value():
        return False
    try:
        import psycopg
        with psycopg.connect(host=config.pg_host, port=config.pg_port,
                             dbname=config.pg_database, user=config.pg_user,
                             password=config.pg_password.get_secret_value(),
                             connect_timeout=3, options="-c statement_timeout=2000") as conn:
            row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            return row == ("0001",)
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
