"""Extra public model for isolated, no-spend platform Chat vertical."""
import sqlalchemy as sa

from ..catalog.schemas import Price
from ..platform_providers import tables as platform
from .schemas import ModelView
from .platform_admission import PLATFORM_MODEL_PREFIX


class PlatformPolicyMixin:
    def public_policy(self, raw):
        base = super().public_policy(raw)
        if not self.platform_demo:
            return base
        with self.engine.begin() as conn:
            record = conn.execute(sa.select(platform.connections).where(
                platform.connections.c.provider == "deepseek")).mappings().first()
        if (not record or not record["enabled"] or record["verified_at"] is None):
            return base
        model = next((item for item in base.models if item.id == record["model"]
                      and item.provider == "deepseek"), None)
        if not model:
            return base
        public_id = PLATFORM_MODEL_PREFIX + record["model"]
        base.models.append(ModelView(id=public_id, provider="platform",
            label="Платформа · " + model.label,
            description="Бесплатный синтетический тест. Не реальный DeepSeek.",
            price=Price(), text=True, vision=False))
        base.default_model = public_id
        base.revision += ":platform-" + str(record["revision"])
        return base
