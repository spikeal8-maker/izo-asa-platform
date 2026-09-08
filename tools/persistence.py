"""Write/read a disposable CI canary; refuses development/production execution."""
import sys
from uuid import UUID
from izo.config import settings
from izo.storage import S3Store

KEY = f"assets/{UUID(int=1).hex}/{UUID(int=2).hex}/ci-canary.txt"
DATA = b"izo-foundation-persistence-canary-v1"


def main(action: str) -> None:
    c = settings()
    if c.environment != "test" or c.pg_database != "izo":
        raise SystemExit("Persistence canary is restricted to the isolated test stack")
    import psycopg
    with psycopg.connect(host=c.pg_host, port=c.pg_port, dbname=c.pg_database,
                         user=c.pg_user, password=c.pg_password.get_secret_value()) as conn:
        store = S3Store(c)
        if action == "write":
            conn.execute("INSERT INTO platform_metadata (key,value) VALUES (%s,%s) "
                         "ON CONFLICT (key) DO UPDATE SET value=excluded.value",
                         ("ci-canary", DATA.decode()))
            store.put(KEY, DATA, "text/plain")
        elif action == "read":
            row = conn.execute("SELECT value FROM platform_metadata WHERE key=%s",
                               ("ci-canary",)).fetchone()
            assert row == (DATA.decode(),)
            assert store.get(KEY) == DATA
        else:
            raise SystemExit("Use write or read")
    print("PERSISTENCE_OK", action)


if __name__ == "__main__":
    main(sys.argv[1])
