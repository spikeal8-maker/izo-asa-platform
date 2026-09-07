# ИЗО АСА · новая платформа

Новая реализация IZO ASA. **Foundation 0: техническое основание, не готовый сервис.**
Старые аккаунты, база, код и Windows-службы сюда не переносятся.
Публичная витрина продукта остаётся в `spikeal8-maker/izo-asa`.

## Что есть

Общая React/TypeScript-оболочка: изображения, видео, звук, 3D, чат, галерея,
лента, аккаунт и административный раздел. Навигация, темы, диалог состояния,
адаптивная вёрстка. Разделы честно помечены как не реализованные.
FastAPI factory, отдельные liveness/readiness, S3-адаптер, PostgreSQL и Alembic,
чистые контракты заданий и возможностей, проверки архитектурных границ.

**Чего ещё нет:** регистрации, балансов, заданий в БД, настоящей генерации,
платежей, подключённого GPU-worker, авторизации Telegram/MAX и production-деплоя.
Обнаружение контейнера Mini App в UI не является авторизацией.

## Первый запуск (локальный development, НЕ рабочий сайт)

Требуются Git, Python 3.13 и Docker Engine/Desktop с Compose v2.

```sh
git clone https://github.com/spikeal8-maker/izo-asa-platform.git
cd izo-asa-platform
git switch foundation/initial-platform
python tools/bootstrap.py
docker compose up --build --wait
```

Открыть **http://localhost:8080**. Первый запуск скачивает зависимости и образы.
Снаружи опубликован только loopback-порт сайта. База и S3 не открываются в интернет.
`bootstrap.py` создаёт случайные локальные пароли в `.env` и никогда не перезаписывает
существующий файл. В Windows защищайте эту папку правами текущего пользователя.

```sh
python tools/smoke.py
docker compose down
docker compose up --wait
```

`down` без `-v` сохраняет именованные volumes. **Не используйте `down -v` для
среды с нужными данными. Volumes не заменяют резервные копии.**

## Быстрые проверки (не зависят от живого сервера)

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

UI (Node 24):
```sh
cd apps/web
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

Тесты UI используют fake API. Реальный backend + PostgreSQL + S3 проверяются
отдельно в Compose. Нет AI-ключей, GPU, почты и production-данных в CI.

## Карта

- `apps/web/src/shell` — общая оболочка, не вся будущая продуктовая логика.
- `apps/web/src/platform` — только platform presentation; signed login будет отдельно.
- `apps/web/src/shared` — HTTP-клиент и generated API types.
- `apps/api/izo/contracts.py` — provider-neutral контракты без инфраструктуры.
- `apps/api/izo/generation.py` — чистые правила выбора исполнителя и состояний.
- `apps/api/izo/storage.py` — приватное S3-хранилище.
- `apps/api/migrations` — миграции; приложение само схему не меняет.
- `packages/contracts` — OpenAPI для генерации TypeScript-клиента.
- `tests`, `apps/web/e2e` — независимые unit/architecture/browser проверки.
- `infra`, `compose.yaml` — только локальный foundation-стенд.

Состояние: [docs/STATUS.md](docs/STATUS.md).
Решения и границы: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Следующий этап: [docs/NEXT.md](docs/NEXT.md).
Правила для агентов: [AGENTS.md](AGENTS.md).

## Лицензирование

Репозиторий публичный, но **не объявлен open source**. В `LICENSE` временно
сохранены права владельца; окончательная лицензия не выбрана. Права GitHub на
хостинг/просмотр/форки и лицензии внешних зависимостей сохраняются.
