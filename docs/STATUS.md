# Фактическое состояние IZO ASA

Срез: 8 сентября 2026. Следующий функциональный пакет — AUTH-001.
Исходная проверенная база: `591416bec096803ab2c0860a356299525f6a3d6d` (UX PR #3).
Работа ведётся в отдельной `auth/server-sessions`; PR #1/#3, main, старый сайт,
его данные, GPU и настоящие AI-ключи не изменяются. MERGED/DEPLOYED: нет.

## Что написано в AUTH-001

Настоящий backend: Account/AuthIdentity/PasswordCredential/Session, одноразовые
приглашения, серверные permissions, журнал успешных auth-команд и DB-rate counters.
Новая Alembic migration0002; исходная0001 не меняется. Регистрация по приглашению,
вход, me, список/отзыв сессий и logout — реальные HTTP API, не DemoProvider.

Пароли — scrypt, bearer в БД хэширован; cookie HttpOnly/SameSite, отдельный CSRF и
строгий Origin. Auth errors не возвращают входные пароли. Роль, баллы и owner
не принимаются из public payload; новая email identity не помечается проверенной.

В UI добавлены только тонкие формы входа/регистрации и аккаунт/сессии. Студия,
её условный баланс и галерея по-прежнему демонстрационные и не объявляются
серверными функциями. Новый дизайн не считается принятым владельцем.

## Проверки

При подготовке локально прошли 43 unit/HTTP/architecture случаев на изолированной
SQLite и fake clock. Это не доказательство PG locking или Docker. Локально проверен
синтаксис новых TS/TSX; полноценные TypeScript/React/browser tests — в GitHub CI.
Прямой сетевой clone недоступен, полный checkout/локальный Docker не запускались.

Расширенный CI содержит настоящую PostgreSQL+HTTP приёмку before/after фактического
Compose down/up, concurrency tests приглашений/identity/session cap и limiter.
Реализация `3dd3c01e8e46fe2b51b392fceb03a723172d3ec2` прошла [CI 34241678240](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/34241678240), job `102113156085`: completed/success. Прочитаны все step summaries: backend, contracts, web build/browser, настоящая PostgreSQL/HTTP/Compose integration и cleanup успешны. Число полного suite этим чтением не подсчитывалось.

Завершающее уточнение README/scope/этого STATUS не меняет runtime или tests.
Его отдельный итоговый SHA/CI фиксируются в PR после проверки; успех кода не
переносится автоматически на любую будущую версию.

Browser tests UI используют fake API; их не называть настоящим end-to-end входом
через production. PG/HTTP gate — отдельное доказательство. Защита public branch,
независимое review, Windows scaling и реальные Telegram/MAX этим пакетом не проверены.

## Где контракт и команды

[Accounts README](../apps/api/izo/accounts/README.md) — маршруты, поля, defaults,
миграция/запуск, приглашение, защита, ограничения и команды приёмки этого модуля.
[Backend AGENTS](../apps/api/AGENTS.md) — короткая карта для следующего агента.
`tools/scopes/auth-001.json` ограничивает изменения 32 файлами, перечисляет чувствительные
миграцию/Compose/CI/bootstrap, необходимые именно для реальной серверной проверки.
Новые зависимости не добавляются. Проверки не отключаются ради зелёного результата.

## Что ещё не реализовано

AUTH-002: почта/проверка адреса/recovery/linking; signed Telegram/MAX; MFA.
CREDIT/ENTITLEMENT/ADMIN: серверные баллы, разрешения моделей и админские начисления.
MEDIA/JOBS: private owner-scoped файлы, persistent jobs/worker; реальные AI/local
подключения; функциональные gallery/feed/chat/video/audio/3D; платежи; production.

Приглашения — закрытый dev/test доступ, не публичный перезапуск. Текущие счётчики
ограничивают попытки в фиксированном окне; за proxy требуется отдельная edge/trust
политика и нагрузочная проверка. Cookie HTTP допускается только на local origin;
публичный HTTPS/production gate не снимается. Независимое рассмотрение и защита
main остаются отдельными организационными gates, не частью существования AGENTS.

Foundation, спецификация U45/D14/A30/AD10/S66 и план NEXT сохраняются. Не создавать
новый общий план перед следующим ограниченным серверным сценарием. Каждая
готовность обозначается отдельно: IMPLEMENTED/TESTED/REVIEWED/PUSHED/MERGED/DEPLOYED.
