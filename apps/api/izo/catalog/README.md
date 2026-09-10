# CATALOG-001 · non-live catalog lifecycle

Первый объём управляет одной существующей OpenRouter image capability и connection metadata.
Draft создаёт immutable revision. Contract proof проверяет adapter/model/resolutions, фиксированный
endpoint, конечные concurrency/rate limits и совпадение credential scope. Сеть не вызывается.
Publish у connection фиксирует revision, но оставляет `disabled`; publish capability не делает
его runtime-доступным. Это позволяет проверить каталог без ключа и внешних расходов.

Credential binding — только metadata: source type, opaque secret_ref, environment/account/project,
version. Raw secret не принимается и не возвращается. Для `env` в текущем объёме разрешена только
ссылка `IZO_OPENROUTER_API_KEY`; значение по-прежнему видит лишь provider worker.

Следующий live-gate должен добавить контролируемый proof/activation со spend cap и secret resolver,
не снимать disabled просто административным bool. Уже принятые jobs используют собственный snapshot.
