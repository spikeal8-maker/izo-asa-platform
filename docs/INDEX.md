# IZO ASA · карта документации

INDEX — **стабильная карта**, а не статус и не roadmap. Здесь нет текущих SHA/PR/«следующего шага».
Текущая точка всегда в [CURRENT](CURRENT.md), machine-plan — в [PLAN.json](PLAN.json).

## Быстрый вход

| Нужно понять | Читать |
|---|---|
| Где проект сейчас / откуда продолжать | [CURRENT.md](CURRENT.md) → [PLAN.json](PLAN.json) → `python tools/project_state.py verify` |
| Где живёт конкретная кнопка/операция | [BLOCK_MAP.json](BLOCK_MAP.json) или `python tools/context.py --task ...` |
| Какой feature/domain читать, если block неизвестен | [CONTEXT_MAP.json](CONTEXT_MAP.json) |
| Как coding-агент должен работать | [DEVELOPMENT.md](DEVELOPMENT.md), кратко — корневой `AGENTS.md` |
| File/context/scope budgets и recurring audit | [MAINTAINABILITY.md](MAINTAINABILITY.md) |
| Как устроена документация | [DOCS_SYSTEM.md](DOCS_SYSTEM.md) |
| Текущий shell/регистрация/Feed/responsive | [UX_PRODUCT_SHELL.md](UX_PRODUCT_SHELL.md) |
| Immutable CI/checkpoint evidence | `CHECKPOINTS.json` — только для provenance |
| Почему выбрана архитектурная линия | `adr/` |
| Что пользователь должен видеть/уметь | [PRODUCT.md](PRODUCT.md) |
| Админка, permissions, settings | [ADMIN.md](ADMIN.md) |
| Визуал/responsive/accessibility | [UX.md](UX.md) |
| Домены, ownership и data boundaries | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Provider/AI runtime/credentials/retry | [AI_RUNTIME.md](AI_RUNTIME.md) |
| Docker/network/release/backup | [OPERATIONS.md](OPERATIONS.md) |
| Последние доказанные технические факты | [STATUS.md](STATUS.md) |
| Package reports | `reviews/` |
| Старые планы/статусы | `history/` — только по явной необходимости |

## Правило маленькой правки

Не открывать PRODUCT/ADMIN/AI_RUNTIME/CHECKPOINTS целиком автоматически.
Сначала block locator → owner/symbol/anchor → окружающий source block.
Если block неизвестен — route + local README. Большой документ нужен только при реальном пересечении границы.
`AMBIGUOUS` безопаснее случайного выбора. Бюджеты контекста определены в `MAINTAINABILITY.md`.
