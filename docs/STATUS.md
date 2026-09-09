# Фактическое состояние IZO ASA

IMAGE-001, 9 сентября 2026. База `cab337ddd2dc6a573b4a5366b071d31e26bd0523`,
PR #12; новая ветка `image/server-workspace`, PR #13. Текущий HEAD и окончательные
Checks находятся в PR. Этот файл не объявляет публикацию или успех заранее.
Main, родительские ветки и рабочий сайт не менялись; MERGED/DEPLOYED — NO.

## Подтверждённая база

JOBS-001: 671 Python, 270 viewport cases, PostgreSQL/S3/worker/restart и npm-audit
прошли в CI34388638041/34388638004. Это не автоматический PASS следующего SHA.
Аккаунты, email proofs с тестовой доставкой, Credits, Entitlements, Admin, Media
и durable Jobs реализованы. Реального AI-провайдера/SMTP/GPU/платежей нет.

## Изменения IMAGE-001

Основные Studio/Jobs/Gallery теперь используют серверные API. Из runtime удалены
DemoState, браузерный кошелёк, вымышленные работы и тестовый SVG-renderer. Возврат к
демо при ошибке API запрещён. Старые документы прототипа остаются историческими.

Цена/размеры/права приходят из серверного контракта. Quote подтверждается человеком;
до submit сохраняются account-scoped operation/quote IDs. Потерянный ответ повторяется
тем же ID после refresh, не новой платной операцией. Повреждённое/недоступное storage
блокирует новую отправку. Jobs list/detail читают реальное состояние, cancel не
выполняет клиентский refund. Terminal/error/reconciliation_required останавливают poll.

Gallery читает свою страницу metadata, поиск ограничен ею. До открытия работы нет
массовой загрузки originals. Detail проверяет PNG/hash/byte bound, Object URL отзывается
при уходе; новая загрузка файла требует fresh session-bound ticket. При401 private UI
очищается. Возврат во вкладку перепроверяет сессию. Пароли/CSRF/pixels не хранятся
в новом sessionStorage. Это не возможность отозвать уже скачанную копию изображения.

Исполнитель пока test.image.v1: диагностический PNG с TEST ONLY, реальная очередь и
серверные тестовые баллы, но не нейросетевая генерация. Backend jobs по умолчанию off.
Неподдержанные input references/delete/publish/thumbnail не представлены как готовые.
Визуальная концепция не считается принятой владельцем.

## Проверка

Review Source выдаёт git-tracked snapshot с tree и blob manifest; исходные227 blobs
подготовительного commit сверены локально. Локальный snapshot — все tracked файлы,
но не полный upstream git history. Прямой сетевой clone недоступен. Docker локально
отсутствует; Node22 отличается от целевого24, npm offline install не нашёл часть cache.
Поэтому локальная проверка не выдаётся за полный locked build.

Написаны новые protocol-based browser scenarios вместо прежних demo assumptions,
guards границ и настоящий browser→API→PostgreSQL/S3→worker сценарий. Новый browser
сам начисляет через Admin UI и отправляет job; отдельный процесс выполняет его;
download hash/balance проверяются до и после реального Compose restart. Другой
пользователь не получает job/asset. Секретные fixture только RUNNER_TEMP, не artifacts.
Прежние backend/acceptance/audit проверки сохранены. Итог нужно прочитать в Checks,
наличие файлов тестов не означает, что они прошли.

## Scope и дальше

Конечный предел34 paths; backend business code, schema, locks, зависимости и лицензия
не меняются. Расширение transport/CI ограничено соединением пользовательского пути.
Ближайший UI-контракт — studio/README.md; карта файлов — apps/web/AGENTS.md.

После успешной приёмки — CHANGE-001 и один согласованный provider API-001.
До публичного выпуска остаются deployment/backup restore/нагрузка/security review,
принятие дизайна/тарифов/retention и реальных Mini Apps. Никакого нового master plan.
