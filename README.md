# ИЗО АСА · OneNode Image Studio

Новая платформа с общими Account / Credits / Entitlements / Jobs / Media для web и будущих клиентов.
README содержит **стабильные команды**, а не текущий roadmap. Каноническая ветка, active package и ограничения
находятся в [`docs/CURRENT.md`](docs/CURRENT.md) и [`docs/PLAN.json`](docs/PLAN.json).

## С чего начать разработчику или coding-агенту

1. Прочитать `AGENTS.md` и `docs/CURRENT.md`.
2. Выполнить `python tools/project_state.py verify` — checkout должен быть потомком точного `branch_from`.
3. Для конкретной правки выполнить `python tools/context.py --task "<задача>"`.
4. При `CONTEXT BLOCK` читать только owner вокруг symbol/anchor + local map/test; route — fallback, не повод сканировать весь feature.

Документация: [INDEX](docs/INDEX.md) — карта; [DOCS_SYSTEM](docs/DOCS_SYSTEM.md) — правила владельцев фактов;
[STATUS](docs/STATUS.md) — доказанные факты; [NEXT](docs/NEXT.md) — человеческое представление PLAN.

## Локальный dev-стенд

Требуются Git, Python 3.13 и Docker Compose v2. Используйте branch, переданный текущим handoff/CURRENT;
README намеренно не закрепляет имя development branch.

```sh
git clone https://github.com/spikeal8-maker/izo-asa-platform.git
cd izo-asa-platform
python tools/bootstrap.py
docker compose up --build --wait
```
Открыть `http://localhost:8080/register`. Bootstrap создаёт только локальные dev/test secrets/config; не использовать
production values в репозитории. Дополнительные workers/providers запускаются только явными Compose profiles и
настройками, описанными в CURRENT/AI_RUNTIME/локальном README соответствующего домена.

Детерминированный `test.image.v1` сохраняется как regression executor. Наличие внешнего provider adapter не означает,
что real key/spend включён. Реальные provider calls, SMTP, payments, bots и production требуют отдельного разрешения.

Обычная остановка:

```sh
docker compose down
```

Не использовать `down -v` как «обновление»: он удаляет локальные volumes. Volumes не являются backup.

## Проверки

Backend:

```sh
python -m pip install -r requirements-dev.txt
python tools/check_docs.py
python -m pytest
python tools/export_contracts.py --check
```

Frontend (`apps/web`, Node version — из текущего CI/runtime policy):

```sh
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```
После малой правки сначала запускается targeted test из context route; полный CI сохраняется перед технической
приёмкой. Mocked browser matrix не доказывает PostgreSQL/S3/restart/provider network — соответствующие integration
gates маркируются отдельно.

## Безопасность и выпуск

Private data/credentials не входят в source artifacts. Review Source — tracked snapshot/manifest, не `.git` и не runtime
окружение. Merge, deployment и live external spend независимы от факта зелёного CI и требуют отдельного решения владельца.

LICENSE не изменяется автоматически из-за публичности репозитория; условия выпуска/лицензии принимаются отдельно.
