# Media · локальная карта домена

Media — единое приватное хранилище пользовательских assets и job outputs. Домен владеет upload/output
allocations, validation, S3 object lifecycle, private metadata, download tickets и ownership checks.
Gallery читает эти assets; Jobs завершает результаты через то же Media-ядро, а не вторую файловую систему.

| Задача | Основной owner | Ближайшие tests |
|---|---|---|
| User upload lifecycle | `service.py` | `test_media.py`, `test_media_http.py` |
| Job output reservation/finalization | `outputs.py` | `test_jobs.py`, `test_media_boundaries.py` |
| Private read/download tickets | reader/routes modules | `test_media_access.py`, `test_media_http.py` |
| Image validation/normalization | `codec.py` | `test_media_codec.py` |
| S3 object IO / uncertainty | `objects.py`, service recovery paths | media acceptance/boundary tests |
| Migration / ownership constraints | media migrations | `test_media_migration.py` |

## Инварианты

- asset ownership проверяется backend на каждом private read/download;
- browser не выбирает object key, owner или внутренний storage URL;
- untrusted image bytes декодируются/нормализуются до ready asset;
- S3 unknown outcome сохраняет durable recovery state, а не освобождает quota наугад;
- Jobs outputs и uploads учитываются в общей storage usage/reservations;
- download ticket короткоживущий и не превращает private asset в public object.

## Текущие границы

Web Gallery уже использует private Media API, а server Jobs сохраняет output в общие assets. Не реализованные
расширения — готовое удаление с dependency policy, public feed/publication, thumbnails и modality-specific viewers.
Они не меняют текущий ownership/storage contract.

- upload/download/storage → `api.media`;
- Job output/cancel/reconcile → `api.jobs`;
- storage quota policy → `api.entitlements`;
- Gallery layout/download UI → `web.gallery`.

Текущие SHA/PR не являются частью local map. Историческая подробная версия сохранена в
`docs/history/local-maps-before-DOC-004C/media.md`.
