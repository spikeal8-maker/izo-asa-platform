"""Encrypted server-owned provider credentials, independent of every user account."""
import sqlalchemy as sa

metadata = sa.MetaData()
connections = sa.Table("platform_chat_connections", metadata,
    sa.Column("provider", sa.String(24), primary_key=True),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("generation", sa.Integer, nullable=False),
    sa.Column("nonce", sa.LargeBinary, nullable=False),
    sa.Column("ciphertext", sa.LargeBinary, nullable=False),
    sa.Column("enabled", sa.Boolean, nullable=False),
    sa.Column("verified_at", sa.BigInteger),
    sa.Column("model", sa.String(64), nullable=False),
    sa.Column("daily_limit", sa.Integer, nullable=False),
    sa.Column("concurrency_limit", sa.Integer, nullable=False),
    sa.Column("last_operation_id", sa.Uuid, nullable=False),
    sa.Column("last_operation_hash", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("provider = 'deepseek'", name="platform_provider_supported"),
    sa.CheckConstraint("revision > 0 AND generation > 0", name="platform_provider_versions"),
    sa.CheckConstraint("daily_limit BETWEEN 1 AND 200", name="platform_daily_bound"),
    sa.CheckConstraint("concurrency_limit BETWEEN 1 AND 10", name="platform_concurrency_bound"),
    sa.CheckConstraint("model IN ('deepseek-flash','deepseek-v4-pro')",
                       name="platform_model_bound"))
