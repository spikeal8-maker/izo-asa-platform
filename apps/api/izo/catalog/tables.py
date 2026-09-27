"""Versioned catalog state and append-only staff mutation evidence."""
import sqlalchemy as sa

from ..accounts.tables import metadata
from .schemas import APPROVED


state = sa.Table("catalog_state", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("default_model", sa.String(64), nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("id = 1 AND revision > 0", name="catalog_state_bound"))

models = sa.Table("catalog_models", metadata,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("provider", sa.String(24), nullable=False),
    sa.Column("modality", sa.String(12), nullable=False),
    sa.Column("label", sa.String(120), nullable=False),
    sa.Column("published", sa.Boolean, nullable=False),
    sa.Column("enabled", sa.Boolean, nullable=False),
    sa.Column("input_kopeks_per_million", sa.BigInteger),
    sa.Column("output_kopeks_per_million", sa.BigInteger),
    sa.Column("image_kopeks_per_image", sa.BigInteger),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("modality IN ('text','image')", name="catalog_modality"),
    sa.CheckConstraint("NOT enabled OR published", name="catalog_enabled_published"),
    sa.CheckConstraint("input_kopeks_per_million IS NULL OR input_kopeks_per_million BETWEEN 0 AND 1000000000000",
                       name="catalog_input_price_bound"),
    sa.CheckConstraint("output_kopeks_per_million IS NULL OR output_kopeks_per_million BETWEEN 0 AND 1000000000000",
                       name="catalog_output_price_bound"),
    sa.CheckConstraint("image_kopeks_per_image IS NULL OR image_kopeks_per_image BETWEEN 0 AND 1000000000000",
                       name="catalog_image_price_bound"))

events = sa.Table("catalog_events", metadata,
    sa.Column("operation_id", sa.Uuid, primary_key=True),
    sa.Column("actor_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
    sa.Column("model_id", sa.String(64), sa.ForeignKey("catalog_models.id"), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False, unique=True),
    sa.Column("fingerprint", sa.String(64), nullable=False),
    sa.Column("reason", sa.String(300), nullable=False),
    sa.Column("before_json", sa.JSON, nullable=False),
    sa.Column("after_json", sa.JSON, nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("revision > 1", name="catalog_event_revision"))


def ensure_test_seed(conn, now: int) -> bool:
    """Only metadata.create_all SQLite fixtures lack the Alembic data seed."""
    if conn.execute(sa.select(state.c.id).where(state.c.id == 1)).first():
        return True
    if conn.dialect.name != "sqlite":
        return False
    conn.execute(sa.insert(state).values(id=1, revision=1,
        default_model="deepseek-flash", updated_at=now))
    conn.execute(sa.insert(models), [dict(
        id=model_id, provider=provider, modality=modality, label=label,
        published=modality == "text", enabled=modality == "text",
        input_kopeks_per_million=None, output_kopeks_per_million=None,
        image_kopeks_per_image=None, updated_at=now)
        for model_id, provider, modality, label in APPROVED])
    return True
