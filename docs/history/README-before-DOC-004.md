# ИЗО АСА · новая платформа

Текущая разработка: **image/server-workspace**, IMAGE-001 / PR #13 поверх серверных
заданий. Старые аккаунты/БД/Windows-службы не переносятся. Это закрытый dev/test,
не готовый публичный AI-сервис. Последний source SHA и результаты — Checks PR.

Аккаунты, сессии, баллы, планы, компенсации, приватные изображения и задания работают
через общий backend. Основные студия, задания и галерея подключаются к этим API,
без браузерного demo ledger. Сейчас только диагностический `test.image.v1`: PNG
с отметкой TEST ONLY, **не нейросеть**. Настоящие AI/SMTP/Telegram/MAX ещё не подключены.

## Документы и правки

[INDEX](docs/INDEX.md) — карта; [STATUS](docs/STATUS.md) — факты;
[NEXT](docs/NEXT.md) — единственный порядок этапов; [AGENTS](AGENTS.md) — правила.
[Серверное рабочее пространство](apps/web/src/features/studio/README.md) — IMAGE-001;
[Jobs](apps/api/izo/jobs/README.md), [Media](apps/api/izo/media/README.md),
[Accounts](apps/api/izo/accounts/README.md), [Email](apps/api/izo/accounts/EMAIL.md).
Дизайн не принят владельцем. Документы требований не означают готовой функции.

## Новый локальный стенд

Нужны Git, Python3.13 и Docker Compose v2:

```sh
git clone https://github.com/spikeal8-maker/izo-asa-platform.git
cd izo-asa-platform
git switch image/server-workspace
python tools/bootstrap.py
docker compose up --build --wait
docker compose run --rm api python -m izo.accounts.invites --hours 24
```

Открыть http://localhost:8080/register. Приглашение не даёт staff-права/баллы/план.
Для тестового выполнения оператор должен явно разрешить `IZO_JOBS_ENABLED=true`
в локальном `.env` и запустить `docker compose --profile jobs up --build --wait`.
Также нужны подтверждённый аккаунт, назначенный план с test.image.v1 и размерами32…512,
а затем компенсационные баллы. Публичное самоназначение этих прав не предусмотрено.
Неполная настройка даёт понятный отказ, не бесплатный неограниченный режим.

Для проверки всего пути CI создаёт изолированные synthetic fixtures через
`tools/image_acceptance.py`, без реальных писем/ключей. Не запускайте acceptance
на рабочей базе. Сценарий требует именно изолированные PostgreSQL/S3 и opt-in test.

При старом `.env`: `python tools/bootstrap.py --auth-only` и
`python tools/bootstrap.py --recovery-only` добавляют только отсутствующие поля.
Тестовые письма доступны оператору через `python -m izo.accounts.test_mail --help`
в API-контейнере; HTTP-mailbox отсутствует. Подробности — accounts/EMAIL.md.

## Проверки

Backend: `python -m pip install -r requirements-dev.txt`, `python -m pytest`,
`python tools/export_contracts.py --check`. Frontend под Node24 из `apps/web`:

```sh
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

После малой UI-правки — ближайший spec/phone+laptop; общий CI перед приёмкой сохраняется.
Mocked viewport не доказывает серверный путь: image-live.mjs проверяет настоящий
browser/API/PostgreSQL/S3/worker, затем повтор после Compose down/up.
Review Source предоставляет tracked snapshot+manifest для воспроизводимого чтения;
не включает `.git`, окружение, node_modules и runtime fixtures.

Обычная остановка — `docker compose down` **без -v**, запуск — `docker compose up --wait`.
`down -v` уничтожает локальные данные и не является обновлением. Volumes не backup.
Merge и deployment требуют отдельного разрешения. Публичная витрина — izo-asa.

## Права

LICENSE не изменён: публичный код не объявлен open source. Условия зависимостей и
права GitHub сохраняются; окончательное решение лицензии принимается отдельно.
