# Следующий этап после Foundation 0

Сначала закрыть приёмку Foundation: CI для точного SHA, lockfiles зависимостей,
проверка Compose после пересоздания, browser evidence и ограничения из STATUS.
Никакого merge или production-deploy только на основании отчёта агента.

Далее VS-001 разбивается на последовательные небольшие PR:

1. Accounts: регистрация, пароль, trusted cookie session, CSRF, rate limits,
   owner-scoped API. Привилегии администратора не выдаются через публичный запрос.
2. Credits: ручное начисление с audit и idempotency, reserve/settle/release,
   конкурентные проверки, тестовые счета. Без реальных платежей.
3. Jobs: схема job/attempt, DB-backed claiming, lease/fencing, recovery и fake
   provider. Worker — отдельный процесс из того же кодового пакета.
4. Image + gallery: UI -> job -> private S3 asset -> owner gallery. Проверить
   перезапуск worker/API, дубликат запроса и отсутствие двойного списания.
5. Один реальный API-adapter. Реальный вызов только с разрешением и бюджетом.

Затем подключаем локальный GPU-исполнитель исходящим HTTPS. До этого не нужно
переустанавливать Windows или менять FRP/DNS старого сайта. Feed и Chat идут
следующими отдельными сценариями, затем Video/Audio/3D.

Telegram/MAX: presentation adapter уже предусмотрен; signed authentication и
нативные проверки делаются после trusted web-session и до публичного запуска.

Проверка стоимости изменения: после первого flow отдельно изменить размещение
кнопки на телефоне, правило доступа к модели и обработку provider error. Записать
затронутые модули, тесты, попытки и реальные токены агента. Не обещать заранее
фиксированную экономию и не мерить качество только количеством тестов.
