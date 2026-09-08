# Фактическое состояние IZO ASA

Срез: 8 сентября 2026. Единственный агрегатор реализации; требования и наличие страниц в реестре не являются готовыми функциями.

## 1. Исходная версия и публикация

Исходная версия DOC-003 — `e3e411b5f95c314edbdf62cf69185e1ecd76abb9`, ветка `foundation/initial-platform`, [PR #1](https://github.com/spikeal8-maker/izo-asa-platform/pull/1). На прочитанном срезе PR открыт/Draft; main — `93d9417070e65cdef16fd729b6c1046d5721061c`, без принятия foundation. Никакого deployment или изменений старого сайта/БД/GPU не выполнялось.

DOC-003 завершает постраничный контракт в этом PR отдельным docs-only коммитом. Его точный итоговый SHA и результат CI фиксируются в Checks/комментарии после публикации, не подставляются в файл самоссылкой до создания коммита.

## 2. Что реализовано в коде

| Область | Состояние |
|---|---|
| FastAPI factory, liveness/readiness | Foundation code |
| PostgreSQL/Alembic baseline и S3 boundary | Проверенный технический storage, не ownership пользовательских файлов |
| React shell, nav/themes/dialog | Техническая оболочка, дизайн владельцем отклонён |
| JobSpec/Capability/AssetRef и routing/state policy | DTO/чистые правила, не durable queue |
| OpenAPI export/generated types, dependency locks | Реализованы |
| Unit/architecture/browser/Compose | Проверки foundation; ограничения ниже |

Нет регистрации/сессий/recovery, работающих permissions/тарифов/ledger/компенсаций; persisted jobs/attempts/worker; user upload/ownership; live providers/credential resolver/local agent; функциональных gallery/feed/chat/video/audio/3D; платежей; настоящих Mini App logins; production release/restore/alerts.

## 3. Что документировано

DOC-001 дал общие спецификации 0.1; DOC-002 уточнил agent/provider/credential и QHD/4K-требования. DOC-003 развивает PRODUCT/ADMIN/NEXT до 0.2 и синхронизирует INDEX, AGENTS и STATUS — **шесть существующих Markdown-файлов**, без новых application code, tests, workflow, Docker, dependencies, secrets и LICENSE.

Постраничные карты: U-01…U-45 и D-01…D-14 в PRODUCT; A-01…A-30, AD-01…AD-10 и S-01…S-66 в ADMIN. Это 45 пользовательских экранов, 14 пользовательских диалогов, 30 административных экранов, 10 административных диалогов, 66 типизированных групп настроек, а не 165 реализованных функций. Назначение, маршруты, доступ, actions/states, defaults/apply semantics и связи с пакетами определены для текущего заявленного scope.

Планы basic/extended/custom, конкретные пути, технические DRAFT значения и семантика ограничений — предлагаемый контракт, не утверждённые владельцем коммерческие тарифы. Значения REQ нужны перед включением соответствующей production-функции. Нет необходимости реализовывать весь реестр до закрытой image-alpha.

## 4. Подтверждённые проверки

Исторический source `5f8f3187897316274e53fc9dd979e5770b80d988`: [run 34158092764](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/34158092764) — SUCCESS; исходная приёмка PR фиксирует 107 unit/architecture, 30 Chromium shell cases, OpenAPI/pip/npm/TypeScript/Vite, Compose с DB/S3 canary, down без -v и up, liveness200/readiness503 при остановке S3.

При подготовке DOC-003 повторно прочитаны run metadata исходного `e3e411b…`: [run 34201076869](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/34201076869) — completed/success. Количество тестов этим чтением заново не подсчитывалось. Успех не переносится автоматически на следующий SHA.

Локальная документационная проверка DOC-003 предназначена только для ID/ссылок/полей/пакетов; её отчёт и docs-only compare закрепляются в PR после выполнения. Она не является доказательством auth/credits/setting consumers. Автотесты AC/AP/SV описаны как будущие acceptance cases; в code suite они этим пакетом не добавлены.

Старые 30 browser cases не проверяют новую QHD/4K/HiDPI-матрицу и реальные Telegram/MAX/iOS. Сохранение volumes не равно восстановлению из backup. CI не утверждает дизайн, смысл правовых условий или безопасность ещё отсутствующих endpoints. Независимый review не выдаётся за самопроверку.

## 5. Открытые решения и следующий результат

Согласовать визуал, коммерческие названия/цены/квоты, первый provider/model/budget, retention/grace/приватность/moderation, окончательную лицензию и публичный scope в нужных этапах. Незакрытые решения не блокируют unrelated fake/UX-разработку.

F0-ACCEPT остаётся следующим техническим шагом. При предыдущем чтении DOC-002 GitHub вернул main protected=false; DOC-003 не настраивает защиту, permissions и review. Наличие AGENTS/CODEOWNERS не обеспечивает запрет обхода. Не выполнять merge без отдельного согласования.

Затем UX-001 — новая студия, результат и галерея по U-ID с QHD2560×1440/UHD3840×2160/HiDPI. Существующий shell не дизайн-референс. Затем AUTH/CREDIT/ENTITLEMENT/ADMIN/MEDIA/JOBS и первый сквозной image flow по NEXT. Не наращивать документацию вместо этих ограниченных результатов.

## 6. Обновление статуса

Вписывать только подтверждённое: source SHA, среда/команда или run, результат и ограничения. IMPLEMENTED/TESTED/REVIEWED/PUSHED/MERGED/DEPLOYED/OPERATIONALLY VERIFIED независимы. Полный roadmap не копируется сюда. Вход — [INDEX](INDEX.md), единственный порядок — [NEXT](NEXT.md).
