# Разработка IZO ASA с coding-агентами

Цель: маленькое изменение требует маленького контекста, а серьёзное изменение получает ровно столько
контекста и проверок, сколько нужно по риску. Текущий package/lineage здесь не хранится.

## 1. Роли

Владелец задаёт пользовательский результат и принимает дизайн, реальные расходы, merge/release.
Implementer локализует задачу, пишет минимальный diff и tests. SELF_REVIEW выполняется тем же агентом
после реализации. Independent reviewer — отдельный проход для высокорисковых изменений.

Это роли процесса, а не требование пяти людей. Самопроверка не называется независимым review.

## 2. LOCATE — найти минимальный контекст

Начало: `AGENTS.md → CURRENT.md → tools/context.py`.

```sh
python tools/context.py --task "сделай кнопку Скачать в галерее шире на телефоне"
python tools/context.py --key web.gallery
```

Читать только `read_first` выбранного route. `expand_if_needed` открывается, когда есть конкретный вопрос,
на который первый набор не отвечает. Если route не найден, открыть INDEX и искать точный visible text,
route, symbol, error code или API path. Не начинать с полного tree/repository scan.

## 3. SCOPE — карточка изменения

До кода зафиксировать: пользовательское `до → после`, package/task ID, base branch/SHA, допустимые пути,
non-goals, инварианты, ближайший test и риск. Для маленькой кнопки отдельная многостраничная спецификация
не нужна; для migration/provider/release нужен отдельный finite scope.
## 4. IMPLEMENT → TARGETED TEST

Для bug сначала воспроизвести failing case; для feature сформулировать acceptance case. Сделать минимальное
связное изменение без рефакторинга соседей «заодно». Затем запустить ближайший test из context route.

Типовой минимум:

| Риск | Ближайшее доказательство |
|---|---|
| Локальный UI/CSS | build/typecheck + затронутый E2E на нужных viewport |
| Общий web transport | зависимые account/admin/studio/gallery specs |
| Domain/API | unit + boundary + HTTP/contract при изменённом API |
| Auth/Credits/permissions | negative access + replay/race/idempotency |
| Jobs/Media | owner isolation + retry/restart/storage uncertainty |
| Provider | fake transport + unknown outcome + cancel/recovery + secret/SSRF boundaries |
| Migration | upgrade chain + current schema + PostgreSQL CI |
| Operations/release | exact artifact + isolated integration + backup/restore/health по scope |

## 5. SELF_REVIEW — обязательный отдельный проход

После реализации нельзя сразу писать «готово». Агент прекращает расширение функции и рассматривает
собственный diff как reviewer. Заполняется короткий шаблон `templates/SELF_REVIEW.md`.

Обязательные вопросы:

1. Я решил исходную задачу, а не соседнюю удобную задачу?
2. Каждый изменённый файл необходим? Есть ли скрытое расширение scope?
3. Что теперь может сломаться: error/race/reload/restart/cancel/permission/cost/privacy?
4. Сохранились ли server-owned identity/price/ownership/idempotency и другие локальные invariants?
5. Не ослабил ли я test, timeout, limit или security guard ради зелёного результата?
6. Есть ли новый contract/migration/generated artifact, который я забыл обновить?
7. Локальный README/context route по-прежнему ведёт к правильному owner/test?
8. Какие утверждения я пока не доказал?

Verdict: `PASS`, `FIX_REQUIRED`, `ESCALATE`. При `FIX_REQUIRED` исправить и повторить self-review.
## 6. Когда нужен независимый review

Обязателен для auth, permissions, Credits/financial semantics, migrations, provider paid lifecycle,
credentials/secrets, cross-account access, release/network policy и изменений общего CI/security boundary.
Для текста, локального CSS и узкого layout обычно достаточно SELF_REVIEW + профильный test + визуальная приёмка.

Independent reviewer получает не весь чат, а task card, diff, изменённые invariants и evidence.
Он не добавляет новые функции в том же проходе; результат — approve/findings/questions.

## 7. Общий CI и публикация

После профильного PASS и self-review: `check_docs`, scope-check, generated contracts, diff/secret sanity,
затем один PR. Общий CI не заменяется локальными тестами. Проверять exact source SHA и реальные steps;
скipped stage не считать проверкой, synthetic merge не называть фактическим merge.

Merge/deploy/live provider call — отдельные действия. Наличие зелёного PR не является разрешением.

## 8. Обновление документации

- Изменился только локальный элемент → обычно локальный README менять не нужно, если ownership прежний.
- Изменилась граница/owner/test → обновить локальный README и `CONTEXT_MAP.json`.
- Изменился package/lineage status → обновить `PLAN.json`, `CURRENT.md`, затем `STATUS.md` фактами.
- Изменился предметный контракт → обновить единственный PRODUCT/ADMIN/UX/ARCHITECTURE/AI_RUNTIME owner.
- Подробный технический отчёт → `reviews/<ID>.md`, а не копия во все документы.

Перед push обязательно `python tools/check_docs.py`.

## 9. Handoff

Передача следующему агенту занимает несколько абзацев: package/task, branch/base, фактический diff,
проверки и их среда, открытые риски и один следующий шаг. Не переносить chain-of-thought, гигантские логи
или весь repository synopsis. Формат — `templates/HANDOFF.md`.
