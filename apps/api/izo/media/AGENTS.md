# MEDIA-001: короткий путь к правке

Наследует корневой AGENTS. Не читать старую IZO_ASA, UI и все планы для одного
исправления загрузки. Вход: README рядом → один файл ответственности → его тест.

- Вход/размеры: schemas.py, test_media.py; распознавание/перекодирование: codec.py,
  test_media_codec.py. Production всегда вызывает отдельный ограниченный процесс.
- Admission/quota/retry: service.py + repository.py, test_media.py/test_media_access.py.
- Владение/скачивание: reads.py, test_media_access.py/test_media_http.py.
- HTTP/origin/body: routes.py/http.py, test_media_http.py; существующие Accounts
  defaults не менять. Доступ к аккаунтам только через accounts/media_access.py.
- S3: objects.py, test_media_boundaries.py. Не выдавать bucket URL или public ACL.
- Migration: только новый файл; 0007 — статическая версия, не импорт runtime tables.

Главные инварианты: cookie identity; отсутствие client owner/URL/secret; Account
lock перед policy/Media; storage reservation в транзакции; никакого Credits mutation;
нет DB lock на всё время codec/S3; sealing до put; unknown write остаётся STORING;
старый validation attempt не может завершить отменённую загрузку; завершённый asset
неизменяем через этот API. Не освобождать allocation неизвестной записи по таймеру.

Тестовый mock decoder в SQL-тестах не заменяет test_media_codec и настоящий S3/PG
сценарий tools/media_acceptance.py. Не считать allowed preflight квот разрешением
worker dispatch. Здесь зарезервированы только bytes загрузки, не ресурсы генерации.

После правки ближайший test, затем полный CI перед приёмкой. Собственный scope
задан tools/scopes/media-001.json; image formats и новые dependencies нельзя
расширять ради удобства. Проверка рабочего сайта/ключей/базы не входит в задачу.
