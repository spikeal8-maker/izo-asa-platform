# IZO ASA · человеческое представление плана

Machine source of truth: [`PLAN.json`](PLAN.json). Этот файл не хранит отдельный набор статусов.
Если текст ниже противоречит PLAN, остановить разработку и исправить документацию.

## Сейчас

**DOC-004 · Agent Development System** — перестроить документацию и процесс так, чтобы маленькая правка
локализовалась через context route и локальный README, а завершённое изменение всегда проходило SELF_REVIEW.

Критерий завершения DOC-004:

- `AGENTS.md` не содержит mutable roadmap/SHA;
- `CURRENT.md` и `PLAN.json` однозначно показывают canonical/active/next;
- `CONTEXT_MAP.json` маршрутизирует основные web/backend/ops/docs области;
- ключевые web features и provider domain имеют локальные карты ownership;
- `tools/context.py` выдаёт минимальный context;
- `tools/check_docs.py` ловит рассинхронизацию;
- tests защищают routing и canonical lineage;
- документационный diff проходит SELF_REVIEW и CI.

## Сразу после

**LINEAGE-001** — не новая функция. Нужно сравнить полезную provider-neutral работу из параллельной
OpenRouter→SETTINGS→CATALOG линии с канонической fal.ai линией. Только осознанно перенести совместимые
части, адаптировать provider-specific assumptions и пометить старые ветки superseded/archived.

До закрытия LINEAGE-001 нельзя автоматически продолжать PR #19/#20/#21 и нельзя начинать следующую
крупную feature поверх одной из двух расходящихся линий.

## Дальнейшие пакеты

Полный реестр IDs, зависимостей и статусов находится только в `PLAN.json`. Предметные критерии старых
пакетов сохранены в `history/NEXT-v0.2-before-DOC-004.md`; агент открывает их только для конкретного ID.
Будущие изменения roadmap делаются сначала в PLAN, затем при необходимости кратко отражаются здесь.
