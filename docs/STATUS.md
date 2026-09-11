# Фактическое состояние IZO ASA

## API-001 — рабочее состояние до remote CI, 11 сентября 2026

Base — `8dd49ba1b5168ed5b9e363672497cca3e308d296` (`change/targeted-maintenance`),
рабочая ветка — `api/fal-klein-001`. В текущем рабочем дереве добавлен первый внешний
provider: fal.ai / `fal-ai/flux-2/klein/4b`, capability `fal.flux2.klein.4b`.
Пакет ещё не объявлен принятым: commit/push/PR и Linux/PostgreSQL GitHub CI должны быть
проверены отдельно. Live fal call, настоящий key и реальные расходы — **NO**.

Существующий Account/Credits/Jobs/Media/Gallery не дублируется. `test.image.v1` сохранён
как deterministic regression-provider. Для fal добавлен durable provider-call lifecycle:
до network submit фиксируется provider intent; после получения сохраняется `request_id`;
restart продолжает тот же request. Потерянный submit response без request ID остаётся
`provider_submission_unknown` и не получает автоматического второго POST. Поздно пришедший
request ID сохраняется даже после истечения старого lease и безопасно возвращает тот же job
в очередь на polling.

External cancel не даёт ложный refund: HTTP202 означает только запрос отмены. Даже локальный
`queued` после recovery не считается доказательством отсутствия provider work, если durable
provider-call уже существует. Terminal release возможен только до provider intent либо после
подтверждённой отмены/определённого failure. Accepted provider request можно сверять после
выключения новых admissions; несовместимая credential version закрывается fail-closed.

Fal key передаётся только отдельному `fal-worker`; API/test-worker его не получают. Unit/browser
network заблокирован. Submit отправляет `X-Fal-Store-IO: 0`; provider media получает ограниченный
TTL, остаётся публичным только на стороне fal в пределах этого TTL, скачивается bounded HTTPS
`fal.media` без redirects и затем переписывается существующим `media.codec` перед private S3.
Это техническая минимизация хранения, не production/privacy approval для пользовательских или
детских данных.

Локально после последних правок: профильные provider/Jobs/recovery/boundary + migration-workflow
**77/77 PASS** на Python3.11.9; `compileall`, OpenAPI consistency, `git diff --check` и scope PASS.
`npm run build` PASS; `provider.spec.ts + studio.spec.ts` — **160/160 PASS** на полной текущей
Playwright viewport-матрице. Scope — **25/26 путей** до этой записи STATUS, после неё ожидается
26/26. Попытка отдельного Linux/Python3.13 запуска через Docker не дошла до тестов из-за зависшей
внешней загрузки образа; процесс остановлен без изменения чужих контейнеров. Поэтому полный
Linux/Python3.13/PostgreSQL/S3/restart gate не считается пройденным до GitHub Actions.

Подробный контракт и ограничения: [API-001](reviews/API-001.md).

---

CHANGE-001, 10 сентября 2026. База — `f2e6f3a29410363412b22ee632e8e1d2e3921ac7`,
ветка image/server-workspace, PR #13. Новый пакет — change/targeted-maintenance.
Точный опубликованный head и окончательные результаты — Checks/комментарий PR.
Main, родительские ветки и рабочий сайт не меняются; MERGED/DEPLOYED — NO.

## Подтверждённая база, не повторная публикация старого пакета

При возобновлении обнаружено, что MEDIA-001, JOBS-001 и IMAGE-001 уже опубликованы.
Устаревший архив MEDIA повторно не применялся. Для source f2e6f3a… прочитан полный лог
Foundation CI34402090357/job102636174543:679 Python,360 viewport cases, все прежние
PostgreSQL/S3/перезапуск и реальный image-browser путь до/после restart — SUCCESS.
Dependency Security34402090422 и Review Source34402090426 — SUCCESS. Synthetic checkout
9780455507029ca600e4508401d8086f1ad12caa имеет tree3a57a9fb1b666c3c57acb21defa979ad29d7a662,
совпадающее с source tree. Скачанный source.tar.gz и231 blobs сверены локально.
В PR #13 записано подтверждение вместо устаревшего ожидания CI. Отдельный Review Source
в действующем коде сохранён; старое описание его удаления не соответствует этой версии.

## Изменения этого пакета

A — кнопка подтверждения показывает серверный резерв и перестраивается на телефоне.
Стабильное доступное имя/описание, touch-height48px; без локального расчёта цены,
глобального масштабирования, переустройства навигации или нового дизайна всей студии.

B — доказана смена доступа через существующую версию плана. После удаления capability
или executor, либо max_action_credits=0, старый ещё не принятый quote отвергается без
нового резерва/задания. Ранее принятые jobs сохраняют snapshot и читаемый результат.
Новая business-логика, коммерческие тарифы и админский редактор планов не добавлялись.
В existing PostgreSQL acceptance добавлен scoped сценарий на синтетическом аккаунте.

C — явный отказ по размеру/бюджету не оставляет студию навечно в неопределённом submit.
rejectedBeforeAdmission проверяет пару status/code. Незнакомый ответ/ошибка500/обрыв
сохраняют тот же operation ID; знакомый код внутри500 также не считается доказанным
отказом. Отдельное сообщение provider_unavailable подготовлено для протокола409,
но это не подключение настоящего AI. Локальные списания/refund/retry provider не добавлены.

## Проверки и воспроизводимость

Локально: 5 новых transactional policy tests — PASS, затем114 профильных tests — PASS,
без failures/errors/skips. Настоящие Accounts/Credits/Entitlements/Jobs с SQLite и fake S3;
отдельная PostgreSQL-проверка находится в существующем Compose gate. Node:27 assertions
классификатора/сообщений и транспиляцииTS — PASS, не полный TypeScript typecheck.
Python3.13.5/FastAPI0.128.2/Alembic1.18.4/Node22 отличаются от locked CI. Полного Docker
и браузеров локально нет; новые browser/PG сценарии не считаются пройденными до Checks.

Исходники восстановлены из git-tracked source artifact, upstream history локально нет.
Точное дерево и blobs проверены; локальный snapshot-коммит не выдаётся за remote source.
Scope проверяется по diff снимка и после публикации по GitHub compare от f2e6f3a….
Цена tokens и полное время работы агента не измерялись. Измерены только число путей,
команды и длительность локальных tests (см. [протокол CHANGE-001](reviews/CHANGE-001.md)); гарантий кратной экономии нет.

## Границы

Конечный scope12 путей, без изменений backend business-code, миграций, dependencies,
Docker-конфигурации, workflow, LICENSE или родительских веток. Три подзадачи выполнены
последовательно; документация дополняет текущие файлы, нового master plan нет.
Исходный IMAGE умеет истинный server job/галерею, но исполнитель только test.image.v1
с PNG TEST ONLY. Нет реальных AI/API-ключей/SMTP/GPU/payments. Визуал не принят владельцем,
OS scaling/настоящие Mini Apps и независимый review не объявлены проверенными.

После принятия CHANGE-001 — API-001 с явно выбранными provider/model/ключом/бюджетом.
До разрешения реальные вызовы не выполняются. Release/backup-restore/security review,
защита main, коммерческие квоты/retention и публичный scope остаются отдельными gates.
