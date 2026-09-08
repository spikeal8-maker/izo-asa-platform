# ИЗО АСА · новая платформа

Новая реализация IZO ASA: общая система изображений, видео, аудио, 3D и чата.
Старые аккаунты, база и Windows-службы сюда не переносятся. Витрина продукта —
`spikeal8-maker/izo-asa`; здесь находится новая реализация.

**Текущий этап — AUTH-001:** серверные аккаунты и сессии в PostgreSQL, технический
Foundation и интерактивный UX-прототип. Это ещё не готовый публичный AI-сервис.
Код этого этапа находится в `auth/server-sessions`, не автоматически в `main`.
Точный проверенный commit/CI и ограничения — [STATUS](docs/STATUS.md) и PR ветки.

## Что действительно работает

Регистрация закрытого стенда по одноразовому приглашению, вход по паролю,
получение своего аккаунта, список активных сессий, отзыв и выход. Пароль хэшируется,
сессия хранится на сервере; браузерный demo-state не предоставляет identity.

Студия, условные баллы и галерея из UX-001 остаются **демонстрацией во вкладке**:
предустановленный SVG не является результатом AI. Письма/подтверждение адреса,
восстановление, настоящий Telegram/MAX login, серверный ledger, медиа/генерации
и production-развёртывание ещё не реализованы. Визуал не принят владельцем.

## Первый запуск — только изолированный development

Нужны Git, Python 3.13 и Docker Engine/Desktop с Compose v2. В новом каталоге:

```sh
git clone --branch auth/server-sessions https://github.com/spikeal8-maker/izo-asa-platform.git
cd izo-asa-platform
python tools/bootstrap.py
docker compose up --build --wait
docker compose run --rm api python -m izo.accounts.invites --hours 24
```

Открыть **http://localhost:8080/register**, ввести выданное приглашение и создать
тестовый аккаунт. Команда показывает одноразовый код намеренно; не публиковать его
в issue или общем логе. Для следующего аккаунта выпустить новый код. Страницы
`/login`, `/account` и `/account/sessions` работают с серверным API.

Если локальный `.env` уже создан предыдущим этапом, не удалять его. В checkout
новой ветки выполнить только добавление отсутствующих auth-настроек:

```sh
python tools/bootstrap.py --auth-only
docker compose up --build --wait
```

Существующие значения не заменяются. В новом dev-стенде bootstrap создаёт случайные
секреты и включает invite signup. Без настроенного auth-secret вход возвращает503,
а регистрация не становится публичной автоматически. База и S3 не открыты наружу;
сайт опубликован только на loopback. Это не production-конфигурация.

```sh
python tools/smoke.py
docker compose down
docker compose up --wait
```

Smoke использует стандартный порт8080. `down` без `-v` сохраняет именованные volumes.
**Не использовать `down -v` с нужными данными. Volumes не заменяют резервные копии.**

## Проверки без production и платных сервисов

```sh
python -m venv .venv
```

Linux/macOS:
```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/python tools/export_contracts.py --check
```

Windows:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe tools/export_contracts.py --check
```

После первой установки для auth-правки достаточно начать с профильного набора:
`python -m pytest tests/test_accounts.py tests/test_auth_boundaries.py` в активной
venv; зависимости не переустанавливать после каждой строки. Полный CI при приёмке
не отменяется.

UI, Node24:
```sh
cd apps/web
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser UI tests используют fake API. PostgreSQL и HTTP проверяются отдельным
Compose gate, включая реальное down/up, гонки приглашений/идентичностей/сессий и
повторное использование отозванной cookie. Нельзя считать SQLite unit или fake
browser тест доказательством PostgreSQL/production-поведения.

## Документы и карта кода

Вход — [INDEX](docs/INDEX.md). [PRODUCT](docs/PRODUCT.md) и [ADMIN](docs/ADMIN.md)
описывают целевые экраны/права/настройки, [NEXT](docs/NEXT.md) — единственный план,
[UX](docs/UX.md) — визуальные требования, [OPERATIONS](docs/OPERATIONS.md) — эксплуатация.
Существующая спецификация0.2 не означает, что все её функции реализованы.

- [Accounts README](apps/api/izo/accounts/README.md) — маршруты, защита, defaults и ограничения AUTH-001.
- `apps/api/izo/accounts` — service/SQL/routes/security, без генерации и ledger.
- `apps/api/migrations` — отдельный Alembic шаг; нет миграций на HTTP startup.
- `apps/web/src/features/accounts` — UI серверного аккаунта; общий транспорт в `shared/api.ts`.
- `apps/web/src/features/prototype` — исключительно demo, не хранилище пользователей.
- `apps/api/izo/contracts.py` и `generation.py` — чистые правила, ещё не durable worker.
- `packages/contracts` — generated OpenAPI; TypeScript типы создаются существующей сборкой.

[AGENTS](AGENTS.md), [backend AGENTS](apps/api/AGENTS.md) и [web AGENTS](apps/web/AGENTS.md)
указывают короткий предметный контекст и профильные tests. Подробности архитектуры
и API/local providers — [ARCHITECTURE](docs/ARCHITECTURE.md), [AI_RUNTIME](docs/AI_RUNTIME.md).

## Лицензирование

Репозиторий публичный, но не объявлен open source. `LICENSE` временно сохраняет
права владельца; окончательная лицензия не выбрана. Права платформы GitHub и
лицензии внешних зависимостей сохраняются. AUTH-001 лицензию не меняет.
