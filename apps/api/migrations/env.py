from alembic import context
from sqlalchemy import URL, create_engine, pool
from izo.config import settings

cfg = settings()
url = URL.create("postgresql+psycopg", username=cfg.pg_user,
                 password=cfg.pg_password.get_secret_value(), host=cfg.pg_host,
                 port=cfg.pg_port, database=cfg.pg_database)
if context.is_offline_mode():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool,
                           connect_args={"connect_timeout": 3})
    with engine.connect() as conn:
        context.configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
