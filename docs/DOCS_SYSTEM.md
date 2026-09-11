# Система документации IZO ASA

Цель документации — не максимальное количество текста, а **минимальный достаточный контекст** для
безопасного изменения проекта человеком или coding-агентом. Документы делятся по времени жизни и
ответственности; один факт не должен иметь двух равноправных владельцев.

## 1. Пять уровней контекста

1. `AGENTS.md` — долговечные правила процесса и безопасности. Не содержит текущих SHA, PR и «следующего шага».
2. `CURRENT.md` + `PLAN.json` — runtime base, точный `branch_from`, working branch, active/next package.
3. `BLOCK_MAP.json` → конкретный UI/API блок по owner/symbol/anchor; `CONTEXT_MAP.json` → fallback до feature/domain.
4. Локальные `AGENTS.md`/`README.md` и затем PRODUCT/ADMIN/UX/ARCHITECTURE/AI_RUNTIME/OPERATIONS — расширение только по необходимости.
5. `reviews/` и `history/` — доказательства и прошлое; они никогда не являются стартовым контекстом обычной правки.

## 2. Единственный владелец каждого типа факта

| Факт | Владелец |
|---|---|
| Runtime base, `branch_from`, working branch, active/next package, parallel lineage | `PLAN.json` |
| Короткое объяснение текущего состояния | `CURRENT.md` (генерируется из PLAN) |
| Конкретный UI/API блок: owner/symbol/anchor/test | `BLOCK_MAP.json` |
| Feature/domain fallback-контекст | `CONTEXT_MAP.json` |
| Как работает процесс разработки и SELF_REVIEW | `DEVELOPMENT.md` |
| Пользовательское поведение/экраны/доступ | `PRODUCT.md` |
| Админские операции/permissions/settings | `ADMIN.md` |
| Визуальные требования | `UX.md` |
| Доменные и data boundaries | `ARCHITECTURE.md` |
| Provider/runtime/credentials/reconciliation | `AI_RUNTIME.md` |
| Архитектурное решение, которое нельзя потерять при смене плана | `adr/ADR-*.md` |
| Docker/release/network/backup | `OPERATIONS.md` |
| Фактически доказанные последние результаты | `STATUS.md` |
| Подробный отчёт отдельного пакета | `reviews/<ID>.md` |

Если информация относится двум темам, один документ владеет правилом, остальные только ссылаются на него.
## 3. Правило чтения — progressive disclosure

Агент не получает право на широкий scan только потому, что репозиторий доступен. Базовый порядок:

`AGENTS → CURRENT/project_state verify → block locator → окружающий source block/test`; если block не найден — `context route → локальный README/AGENTS → source/test`.

Большой предметный документ открывается только если локальная карта прямо на него ссылается или
конкретный вопрос нельзя решить по локальному контракту. Сначала искать точный route/текст/symbol/error,
затем читать небольшой диапазон. Lockfiles, generated contracts, history и чужие feature по умолчанию закрыты.

Для мелкой UI-правки целевой начальный бюджет — обычно 3–6 исходных/тестовых файлов. Это не жёсткий
лимит correctness: если реальная зависимость требует больше, агент объясняет причину и расширяет scope.

## 4. Локальные README как карта блока

Каждый самостоятельный feature/backend domain должен иметь короткий README рядом с кодом. README отвечает:

- какие маршруты/видимые блоки или команды принадлежат модулю;
- какой файл владеет каким элементом;
- какие зависимости являются внешними и не должны дублироваться;
- какие инварианты нельзя нарушить;
- какой ближайший тест запускать;
- куда расширять чтение, если задача пересекает границу.

README не превращается в журнал изменений и не копирует PRODUCT/ARCHITECTURE целиком.

## 5. План, ветки и frozen checkpoints

`PLAN.json` различает `runtime_base`, точный `branch_from` и `working_branch`. Runtime base может быть старше
последнего development checkpoint; новую ветку всегда создают от `branch_from`, а не «самой новой на вид» ветки.
Ровно один package имеет статус `active`, следующий — `planned_next`. Parallel lineage fail-closed.

После успешного exact-head CI checkpoint **замораживается без дополнительного status commit**. Следующий package
создаёт новую ветку точно от frozen SHA и уже в новой ветке переводит предыдущий package в `technical_pass` через
`tools/project_state.py start`. Так зелёный SHA никогда не становится устаревшим из-за «последней правки статуса».

Если появляются две реализации одного package ID, feature work останавливается до reconciliation package.
## 6. Документ — часть Definition of Done

Правка считается документально завершённой, когда:

1. `tools/check_docs.py` проходит;
2. block locator/route для затронутой области всё ещё ведёт к существующему owner/anchor/tests;
3. новый самостоятельный feature/domain имеет local README и покрыт хотя бы одним route; ключевые действия получают block ID;
4. локальный README отражает новое ownership/поведение, если граница реально изменилась;
5. PLAN/CURRENT меняются только в новой ветке при старте следующего package, не после freeze;
6. STATUS обновляется только подтверждёнными фактами, не будущими обещаниями;
7. старый текст, потерявший актуальность, архивируется или явно маркируется historical/superseded.

## 7. Что запрещено

- Создавать ещё один `MASTER_PLAN`, `ROADMAP_FINAL`, `NOW2` или аналогичный второй source of truth.
- Хранить текущий SHA/PR/next package в `AGENTS.md`, INDEX или локальном README.
- Писать в STATUS «готово», пока exact-head проверки ещё идут.
- Использовать review/history как инструкцию текущей разработки.
- Делать documentation-only PR поводом для скрытого изменения runtime/CI/security policy.
- Увеличивать context/scope лимит автоматически после ошибки вместо новой диагностической гипотезы.

## 8. Автоматические предохранители

`tools/context.py` сначала ищет block-level locator и только затем feature/domain route; близкие кандидаты дают
`AMBIGUOUS`, а не случайный выбор. `tools/project_state.py` различает runtime base / branch_from / working branch.
`tools/check_docs.py` проверяет PLAN/CURRENT, block owner+anchor, route paths, local-map coverage, stable docs и UTF-8.
Routing regression corpus содержит нормальные, голосовые, неоднозначные и unsupported запросы.

Эти проверки не заменяют смысловой review. Они делают рассинхронизацию заметной раньше, чем следующий
бот начнёт разработку не от той ветки или прочитает половину репозитория.
