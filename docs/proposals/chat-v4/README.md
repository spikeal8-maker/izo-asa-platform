# IZO ASA Chat v4 documentation pack

**Статус пакета:** APPROVED SOURCE SNAPSHOT · ADOPTED INTO CANONICAL OWNERS · NON-CANONICAL FOR FUTURE IMPLEMENTATION.

Пакет сохраняется как provenance/evidence. Будущая реализация начинает с canonical owners и current state, а этот каталог открывается только при provenance/challenge-review необходимости.

В пакет входят пять review-артефактов:

1. `IZO_ASA_CHAT_PRODUCT_SPEC_v4.md` — стабильное продуктовое ТЗ: что должен уметь Chat и когда он принят.
2. `IZO_ASA_CHAT_ARCHITECTURE_CONTRACT_v4.md` — архитектура данных, providers/tools/files, Context Engine, code/file ownership и target module structure.
3. `IZO_ASA_CHAT_ENGINEERING_MAINTENANCE_v4.md` — file budgets, split-before-growth, cleanup, garbage policy и регулярные structural audits.
4. `IZO_ASA_CHAT_V4_ADOPTION_TRACEABILITY.md` — переход из текущего GitHub-состояния в v4 и requirement→owner/test mapping.
5. `IZO_ASA_PLATFORM_SOURCE_DELIVERY_CONTRACT_v1.md` — platform-level source-first/donor policy и карта VISIBLE/FUNCTIONAL/ACCEPTED для Chat/Admin/Image/Gallery/Feed/Video/Audio/3D.

`ADOPTION_TRACEABILITY` и `PLATFORM_SOURCE_DELIVERY_CONTRACT` — переходные review-источники и не должны становиться новым постоянным ROADMAP/NOW. После approval их факты распределяются по существующим owners (`#222`, PRODUCT, UX, ARCHITECTURE, AI_RUNTIME, ADMIN, MAINTAINABILITY, DOCS_SYSTEM, PLAN/CURRENT).