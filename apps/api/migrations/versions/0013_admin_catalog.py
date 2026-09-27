"""Finite staff catalog and append-only display-price change audit."""
from alembic import op
import sqlalchemy as sa

revision = "0013_admin_catalog"
down_revision = "0012_chat"
branch_labels = depends_on = None


def upgrade():
    op.create_table("catalog_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("default_model", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("id = 1 AND revision > 0", name="catalog_state_bound"))
    op.create_table("catalog_models",
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
    op.create_table("catalog_events",
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
    state = sa.table("catalog_state", sa.column("id", sa.Integer),
        sa.column("revision", sa.Integer), sa.column("default_model", sa.String),
        sa.column("updated_at", sa.BigInteger))
    models = sa.table("catalog_models", sa.column("id", sa.String),
        sa.column("provider", sa.String), sa.column("modality", sa.String),
        sa.column("label", sa.String), sa.column("published", sa.Boolean),
        sa.column("enabled", sa.Boolean), sa.column("updated_at", sa.BigInteger))
    op.bulk_insert(state, [{"id": 1, "revision": 1,
                            "default_model": "deepseek-flash", "updated_at": 0}])
    op.bulk_insert(models, [
        {"id": "deepseek-flash", "provider": "deepseek", "modality": "text",
         "label": "DeepSeek Flash", "published": True, "enabled": True, "updated_at": 0},
        {"id": "deepseek-v4-pro", "provider": "deepseek", "modality": "text",
         "label": "DeepSeek V4 Pro", "published": True, "enabled": True, "updated_at": 0},
        {"id": "fal.flux2.klein.4b", "provider": "fal", "modality": "image",
         "label": "FLUX.2 Klein 4B", "published": False, "enabled": False, "updated_at": 0},
    ])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION catalog_events_immutable() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'catalog events are immutable'; END;
            $$ LANGUAGE plpgsql""")
        op.execute("""CREATE TRIGGER catalog_events_no_change BEFORE UPDATE OR DELETE
            ON catalog_events FOR EACH ROW EXECUTE FUNCTION catalog_events_immutable()""")
        op.execute("""CREATE TRIGGER catalog_events_no_truncate BEFORE TRUNCATE
            ON catalog_events FOR EACH STATEMENT EXECUTE FUNCTION catalog_events_immutable()""")
    elif op.get_bind().dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(f"""CREATE TRIGGER catalog_events_no_{action.lower()}
                BEFORE {action} ON catalog_events BEGIN
                SELECT RAISE(ABORT, 'catalog events are immutable'); END""")


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM catalog_events")).scalar_one()
    if count:
        raise RuntimeError("populated catalog audit cannot be downgraded")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER catalog_events_no_truncate ON catalog_events")
        op.execute("DROP TRIGGER catalog_events_no_change ON catalog_events")
        op.execute("DROP FUNCTION catalog_events_immutable()")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER catalog_events_no_update")
        op.execute("DROP TRIGGER catalog_events_no_delete")
    op.drop_table("catalog_events")
    op.drop_table("catalog_models")
    op.drop_table("catalog_state")
