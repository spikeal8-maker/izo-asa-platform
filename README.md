# ИЗО АСА · новая платформа

Новая реализация IZO ASA. Старые аккаунты/БД/Windows-службы не переносятся.
Текущая разработка — ветка **auth/email-recovery**, поверх AUTH-001 и UX-прототипа.
Это **закрытый dev/test, не готовый AI-сервис и не разрешение публичного запуска**.

Есть реальные серверные аккаунты/сессии, приглашения, подтверждение email, сброс/смена
пароля с отзывом сессий. Доставка писем пока только тестовая, доступная оператору.
Баланс, задания и работы в студии — демо браузера, не server ledger или облачная галерея.
Нет real AI, signed Telegram/MAX, payments, identity linking, SMTP или production deployment.

## Документы

[INDEX](docs/INDEX.md) → карта продукта; [STATUS](docs/STATUS.md) → факты;
[NEXT](docs/NEXT.md) → единственный план;
[Accounts](apps/api/izo/accounts/README.md) → AUTH-001;
[Email security](apps/api/izo/accounts/EMAIL.md) → AUTH-002, API/проверки/ограничения.
[AGENTS](AGENTS.md) → правила разработчика; [Backend AGENTS](apps/api/AGENTS.md) → краткая карта source/tests.
[PRODUCT](docs/PRODUCT.md), [ADMIN](docs/ADMIN.md), [UX](docs/UX.md),
[ARCHITECTURE](docs/ARCHITECTURE.md), [AI_RUNTIME](docs/AI_RUNTIME.md),
[DEVELOPMENT](docs/DEVELOPMENT.md), [OPERATIONS](docs/OPERATIONS.md) — спецификации,
а не обещание уже работающих функций. Дизайн не принят владельцем.

## Новый локальный стенд

Git, Python3.13 и Docker с Compose v2:

```sh
git clone https://github.com/spikeal8-maker/izo-asa-platform.git
cd izo-asa-platform
git switch auth/email-recovery
python tools/bootstrap.py
docker compose up --build --wait
docker compose run --rm api python -m izo.accounts.invites --hours 24
```

Открыть http://localhost:8080/register и ввести выданное одноразовое приглашение.
Не публиковать приглашение, cookies, .env и коды писем. База/S3 не открываются наружу.
Secrets создаются локально и не печатаются; тестовые письма не отправляются по сети.

## Уже существующий .env

```sh
python tools/bootstrap.py --auth-only
python tools/bootstrap.py --recovery-only
docker compose up --build --wait
```

Добавляются только отсутствующие поля; старые secrets/disabled не заменяются.
Для просмотра запрошенного письма: справка `python -m izo.accounts.test_mail --help`
в API-контейнере; нужны UUID аккаунта и явный `--show-sensitive`. HTTP mailbox нет.
Подробнее — accounts/EMAIL.md. При выключенном канале recovery отвечает503, а не
сообщает о якобы отправленном письме. Реальная доставка — отдельная интеграция.

## Проверки и остановка

Создать venv и установить закреплённые `requirements-dev.txt` только при новом checkout:

```sh
python -m venv .venv
```

После активации venv:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
python tools/export_contracts.py --check
```

UI при установленном Node24, из `apps/web`:

```sh
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

Unit/UI без real AI/GPU/SMTP; PostgreSQL races/restart отдельно проверяются Compose CI.
Для обычной остановки `docker compose down` **без -v**; затем `docker compose up --wait`.
Volumes не backup; `down -v` удалит локальные данные и не является способом обновления.
Source SHA/CI/merge/deploy указываются раздельно. Публичная витрина — `spikeal8-maker/izo-asa`.

## Права

LICENSE не изменён: репозиторий публичный, но не объявлен open source; окончательная
лицензия не выбрана. Условия зависимостей и права GitHub сохраняются.
