# IZO ASA · карта документации

INDEX — **стабильная карта**, а не статус и не roadmap. Здесь не должно быть текущих SHA, PR или фразы
«следующий шаг». Текущая точка всегда в [CURRENT](CURRENT.md), machine-plan — в [PLAN.json](PLAN.json).

## Быстрый вход

| Нужно понять | Читать |
|---|---|
| Где проект сейчас / откуда продолжать | [CURRENT.md](CURRENT.md) → [PLAN.json](PLAN.json) |
| Какие файлы нужны для конкретной правки | [CONTEXT_MAP.json](CONTEXT_MAP.json) или `python tools/context.py` |
| Как coding-агент должен работать | [DEVELOPMENT.md](DEVELOPMENT.md), кратко — корневой `AGENTS.md` |
| Как устроена сама документация | [DOCS_SYSTEM.md](DOCS_SYSTEM.md) |
| Почему выбрана текущая архитектурная линия | `adr/` (сначала ADR-001) |
| Что пользователь должен видеть/уметь | [PRODUCT.md](PRODUCT.md) |
| Админка, permissions, settings | [ADMIN.md](ADMIN.md) |
| Визуал/responsive/accessibility | [UX.md](UX.md) |
| Домены, ownership и data boundaries | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Provider/AI runtime/credentials/retry | [AI_RUNTIME.md](AI_RUNTIME.md) |
| Docker/network/release/backup | [OPERATIONS.md](OPERATIONS.md) |
| Последние доказанные технические факты | [STATUS.md](STATUS.md) |
| Подробные package reports | `reviews/` |
| Старые планы/статусы | `history/` — только по явной необходимости |

## Правило для маленькой правки

Не открывать PRODUCT/ADMIN/AI_RUNTIME целиком автоматически. Сначала context route и локальный README
рядом с кодом. Большой документ нужен только при пересечении предметной границы.

Пример: UI Studio → `apps/web/AGENTS.md` → `features/studio/README.md` → component/CSS/spec.
Backend Jobs → `apps/api/izo/jobs/AGENTS.md` → `jobs/README.md` → конкретный service/execution/test.
