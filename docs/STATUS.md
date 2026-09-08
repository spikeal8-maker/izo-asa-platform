# IZO ASA · фактическое состояние

Срез 8 сентября 2026. Требования не равны реализованным возможностям. Foundation остаётся в PR #1, исходная версия нового UI-пакета — `077bfdb8862a5bbf783b2e483f22b91ca10db3df`. UX-001 разрабатывается отдельно в `ux/studio-gallery`. Main, рабочий сайт, данные и GPU не менялись; merge/deploy не выполнялись.

## Новый пакет: UX-001 + экономная разработка

Реализован интерактивный **демо-прототип**, ещё не утверждённый владельцем дизайн. Работают студия, локальный preview исходника, выбор демо-модели/пропорций, подтверждение условной цены, демонстрационные success/error/cancel, галерея/фильтр/поиск, подробный просмотр, скачивание SVG-примера, повторное использование настроек и удаление. Пустая галерея не заполнена чужими вымышленными работами.

Демо использует предустановленную оригинальную векторную композицию, НЕ генерирует изображение из prompt и НЕ обрабатывает загруженный исходник. Об этом сообщается на странице, перед запуском и в результате. Настоящих баллов, авторизации, ownership или admin API нет. Пример карточки админки — только вымышленные данные.

Демо-состояние ограничено 24 работами и хранится в sessionStorage этой вкладки; запрет/повреждение storage обрабатывается. Перезапуск реального сервера и multi-device sync этим не доказываются. Изображения/file blobs не сохраняются в sessionStorage; локальный upload только для preview. Повтор submit guarded синхронно; терминальная обработка idempotent только в пределах демо.

UI разделён на shell, shared/ui, studio, gallery и изолированный prototype. Зависимости npm/Python, OpenAPI/сервер, БД, Docker, workflow и лицензия не изменены. Старые shell scenarios сохранены, новые browser tests добавлены.

## Правила и экономия

Корневой AGENTS сокращён и структурирован с сохранением safety/ownership/runtime/review правил. Добавлен scoped apps/web/AGENTS с картой «что менять → где искать → ближайший test». Это уточнение, не конкурирующий master plan. Пользователь явно поручил укрепить правила в этом пакете.

`tools/check_change.py` проверяет конечный scope относительно полного согласованного SHA: committed + staged + unstaged + untracked (не ignored), удаление и обе стороны rename. Возвращает отказ при чужих файлах/неразрешённых sensitive paths/превышении лимита. Печатает рекомендуемые проверки, **не запускает их**; unknown area требует полный CI, а не пропуск. Это помощник и evidence, не branch protection и не универсальный affected-test router.

Правила выбора context/test, лимит первоначального чтения, остановка повторной неудачной попытки и краткий handoff записаны в AGENTS. Runtime limits и CI не ослаблялись ради экономии. Фактической telemetry tokens/стоимости здесь нет; процент экономии не заявляется.

## Проверки текущего пакета

Добавлены browser cases studio/gallery и 4 профиля: QHD2560×1440, UHD3840×2160, DPR1.5 и DPR2. Вместе с прежними шестью это 10 профилей Chromium. Реальные Windows OS scaling125/150/200%, iOS и Telegram/MAX не имитируются одним DPR и пока не проверены.

Добавлены Python regression tests scope guard (включая временный git repo, untracked/delete/rename, sensitive paths и file budget) и конкретных web-boundaries. Проверки описанных новых функций считаются выполненными только после фактических результатов CI. Exact head/tree, результаты, screenshot review и ограничения фиксируются в PR после чтения логов. Эта строка не объявляет будущий запуск зелёным.

Локальный сетевой git clone недоступен (DNS failure), пакеты и Docker локально не запускались. Источники прочитаны через GitHub connector; новые файлы пишутся Git tree API. Build/browser/полный suite выполняются на GitHub. Remote compare заменяет локальный scope запуск в этой среде, но тесты самого инструмента входят в существующий pytest gate.

## Предыдущая приёмка основания

F0-ACCEPT source `077bfdb…`: run34219197332, job102038057830 — SUCCESS. Проверен synthetic merge96f013f… с тем же tree0d6eaa…: 131 Python tests, 30 прежних Chromium cases, build, Compose/PostgreSQL/S3 persistence и health. В F0 исправлены revision readiness, Alembic template, safe error response и config diagnostics. Эти результаты относятся к той версии, не автоматически к новому UI.

## Ограничения и следующий результат

Самопроверка не независимое review. Main protection не настроена; широкий write-token способен обойти инструкции. PR/ветки не merged, production не развёрнут. Новый UI должен получить визуальную приёмку владельца. После неё — ограниченный AUTH-001 и реальный первый image flow по NEXT. Не считать демо-галерею готовой системой хранения пользователей.

Нет настоящих accounts/sessions/permissions/entitlements/ledger/compensation, durable jobs/worker, live AI/credentials/local agent, функциональных feed/chat/video/audio/3D, платежей или Mini App logins. Документация v0.2 и общий runtime-контракт сохранены. Дальнейший порядок — NEXT, предметные требования — PRODUCT/ADMIN/UX/AI_RUNTIME, не ещё один план.

## Проверить прототип после получения ветки

```sh
git clone --branch ux/studio-gallery https://github.com/spikeal8-maker/izo-asa-platform.git
cd izo-asa-platform
python tools/bootstrap.py
docker compose up --build --wait
```

Адрес стенда: http://localhost:8080/image. Это локальный dev-прототип, не public deploy. В полноценном checkout для проверки scope:

```sh
python tools/check_change.py --base 077bfdb8862a5bbf783b2e483f22b91ca10db3df --scope tools/scopes/ux-001.json
```

Команды создания .venv и профильных tests — README и apps/web/AGENTS.md. Не удалять volumes с нужными данными. Для каждого отчёта разделять IMPLEMENTED/TESTED/PUSHED/REVIEWED/MERGED/DEPLOYED.
