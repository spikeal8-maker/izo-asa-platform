# OpenRouter Images adapter · API-001

Используется только dedicated `POST https://openrouter.ai/api/v1/images`. API/UI не получают
`IZO_OPENROUTER_API_KEY`; секрет передаётся только отдельному provider-worker. Возможность
по умолчанию выключена. До включения оператор явно задаёт model, product price и проверенные
resolution tiers; реальный вызов и бюджет требуют отдельного разрешения владельца.

Job хранит execution snapshot (adapter/connection/model/resolution/output format/product price),
поэтому изменение env не перенаправляет уже принятую работу на другую модель. Сетевой сбой,
HTTP error или неверный ответ после dispatch считаются неопределённым внешним исходом: worker
не делает автоматический повтор и не освобождает резерв. Test executor остаётся отдельным pool.

Adapter принимает только base64 PNG/JPEG/WebP, ограничивает JSON/image bytes и передаёт результат
через общий media codec/S3. Redirect не следует: bearer key нельзя перенести на другой host. Prompt —
данные, не shell/workflow. Response body и ключи не логируются. Полученный provider receipt/cost
фиксируется до S3 put, чтобы безопасное чтение уже сохранённого объекта не требовало второго AI-вызова.
Точный provider cost из `usage.cost` сохраняется как диагностическая стоимость, но продуктовые
баллы фиксируются серверной quote. Это не платёжная сверка и не hard USD budget.

Проверки: `pytest tests/test_openrouter_provider.py tests/test_jobs.py tests/test_jobs_http.py`.
Live probe отсутствует в CI и не должен добавляться с реальным ключом. Перед первым live acceptance
нужен отдельный OpenRouter key с provider-side spending limit, выбранные model/resolution/product price и
малый разрешённый бюджет; одного env-флага enabled недостаточно как операционного разрешения.
Актуальный контракт API сверять с официальной документацией OpenRouter при каждом изменении адаптера.
