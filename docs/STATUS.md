# Фактическое состояние IZO ASA

Срез документации: 7 сентября 2026. Этот файл — единственный агрегатор состояния, не список обещаний.

## 1. Код и публикация

Foundation source: `5f8f3187897316274e53fc9dd979e5770b80d988`, ветка `foundation/initial-platform`, [PR #1](https://github.com/spikeal8-maker/izo-asa-platform/pull/1).

На момент подготовки DOC-001: PR открыт/Draft, не merged; main содержит начальное уведомление о сохранении прав. Production deployment не выполнялся. Старый сайт и его данные не изменялись. Новую текущую версию нужно сверять с GitHub, а не считать этот исторический SHA вечным HEAD.

DOC-001 дополняет этот PR документацией 0.1, не меняя application code, tests, dependencies, CI, Docker или LICENSE. Результат проверки нового документационного SHA фиксируется в Checks/описании PR после фактического запуска; успех исходного SHA ниже не автоматически переносится на новый.

## 2. Что реально реализовано

| Область | Состояние |
|---|---|
| FastAPI factory, отдельные liveness/readiness | Код foundation, проверен |
| PostgreSQL/Alembic baseline и S3 boundary | Код foundation, проверен в Compose |
| React shell, навигация, themes/dialog, адаптивная структура | Техническая оболочка, не принятый дизайн |
| JobSpec/Capability/AssetRef, routing/state policy | Только DTO/чистые правила |
| OpenAPI export/TypeScript types, dependency locks | Реализованы |
| Unit/architecture/Chromium shell/Compose tests | Реализованы; границы coverage ниже |
| PRODUCT/ADMIN/UX/AI_RUNTIME/ARCHITECTURE/DEVELOPMENT/OPERATIONS/NEXT/INDEX | Спецификация 0.1 в DOC-001; не реализация перечисленных функций |

## 3. Проверенные доказательства foundation

[CI run 34158092764](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/34158092764), job `101853992704`, source head `5f8f3187897316274e53fc9dd979e5770b80d988` — **SUCCESS**. Метаданные и реальные steps повторно прочитаны при подготовке DOC-001. Детализация исходной приёмки сохранена в PR #1.

- 107 unit/architecture проверок, OpenAPI consistency, pip check.
- npm ci, TypeScript/Vite build.
- 30 Chromium shell cases: пять сценариев на шести viewport.
- Compose build/start, migrations, PostgreSQL/S3 canary write.
- down без -v, новый up и чтение DB/object canary.
- Остановка S3: API liveness 200, readiness 503.

107 — параметризованные проверки, не 107 функций. 30 — shell/viewport checks, не реальный Telegram/MAX/iOS. Пересоздание volumes-потребителей не доказывает восстановление из backup. DTO unit tests не доказывают durable queue или безопасность ещё отсутствующих user endpoints.

Первоначальный npm peer conflict исправлен совместимой версией TypeScript, без force/legacy-peer-deps; locks закреплены. Локальные проверки прошлого сеанса не подменяют GitHub Docker/browser run.

## 4. Что не реализовано

Регистрация, trusted web-session, email verification/recovery, Telegram/MAX signed login; credits/ledger; административная компенсация; jobs/attempts в БД и worker; пользовательские media uploads/private ownership; реальные AI providers и local agent; галерея/лента как функции; чат; video/audio/3D; payments; real bot/mail delivery; production release/backup/alerts.

Пустая страница /admin не предоставляет администрирование. S3Store без Accounts не является готовой системой доступа к пользовательским файлам.

## 5. Решение по визуалу

Владелец указал, что нынешний визуал неприемлем. Скриншоты остаются доказательством существования оболочки, не согласованной художественной концепцией. Следующая пользовательская задача — **UX-001** по NEXT: одна новая концепция студии/результата/галереи с интерактивной проверкой на телефоне/планшете/desktop.

## 6. Незакрытые gates

Независимый review и merge Foundation; branch protection/required checks (CODEOWNERS не равен защите); утверждение дизайна; точные product policies/provider/budget; окончательная licence/third-party notices; production image digests/HTTPS/secrets; backup restore и safe release; реальные Mini Apps и нагрузка.

Не создавать отдельный бизнес-блокер из каждого будущего вопроса: только gate следующего пакета может запрещать этот пакет. Например, неопределённая цена video не мешает бесплатному image UX-прототипу.

## 7. Как обновлять

В том же ограниченном пакете обновлять реализованное поведение и подтверждённые проверки, а не переносить весь roadmap сюда. Для evidence указывать SHA, среду, команду/run и результат. IMPLEMENTED / TESTED / REVIEWED / MERGED / DEPLOYED / OPERATIONALLY VERIFIED не объединяются.

Ближайшие действия и критерии — [NEXT](NEXT.md). Вход в комплект — [INDEX](INDEX.md).
