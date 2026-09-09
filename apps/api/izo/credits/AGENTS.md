# Credits — небольшие безопасные изменения

Наследует корневой и backend AGENTS. Сначала README этого модуля и нужный test, не весь проект.

| Задача | Начать с | Проверка |
|---|---|---|
| Amount/DTO/лимит поля | schemas.py | test_credits.py, type/bounds cases |
| Grant/резерв/settle/release | service.py | test_credits.py, replay/rollback/negative cases |
| SQL/ledger/FK | tables.py + repository.py | migration comparison; затем настоящая PG acceptance |
| Своя история через API | routes.py | test_credits_http.py; generated OpenAPI |
| State/permission identity | ../accounts/credit_access.py | denied/expiry/state tests |

Не изменять auth/password/session implementation для кнопки баланса. Только existing server identity; никаких requested role/owner/price из browser. Нет публичных mutate endpoints до отдельного Jobs/Admin scope. Клиентский DemoState не является ledger.

Не использовать float, отрицательное начисление, commit внутри сервиса, прямое редактирование старого ledger или очистку trigger ради теста. Сохранять порядок locks и outer transaction. На unknown outcome AI нельзя автоматически делать release+новую платную задачу — reconciliation принадлежит Jobs.

После малой правки — затронутый case; перед приёмкой полный CI. Не менять dependency lock/стоимость/лимиты тестов без отдельного основания. Новый эндпоинт → экспортировать OpenAPI штатным tool. Подготовленный тест и SQL-render не называть пройденным PG/HTTP/restart. Фактическую экономию tokens не выдумывать.
