# IZO ASA UX v4 / FRONTEND-001 — критический анализ

Статус: **staging critical review / не canonical decision**.

Проверено против frozen source `ux/frontend-reset@5c0e79b6fc3a7120207d0889b176fbfed3dab973`, PR #36, canonical `DOCS_SYSTEM.md`, `MAINTAINABILITY.md`, `PRODUCT.md`, `UX.md`, текущего `project_state` tooling и staging UX v4.

## Итог

Техническая безопасность проекта заметно выше, чем визуальная/документационная зрелость: Image/Jobs/Auth/Media boundaries защищены, exact-head CI и review gates продуманы. Но подготовка UX v4 стала **слишком тяжёлой и многослойной**. Главный новый риск — не отсутствие документации, а её избыток, дублирование и появление параллельного staging-мира, который coding-agent может принять за второй source of truth.

Если продолжать наращивать документы тем же способом, мы начнём воспроизводить именно ту проблему, ради борьбы с которой существуют `DOCS_SYSTEM.md` и `MAINTAINABILITY.md`: маленькая правка снова потребует прочитать слишком много контекста.

## Критические находки

| Severity | Находка | Почему это проблема | Требуемое действие |
|---|---|---|---|
| **HIGH** | Canonical route/UX facts сейчас распределены между `PRODUCT.md`, `UX.md`, `UX_PRODUCT_SHELL.md`, runtime code и staging decisions | `DOCS_SYSTEM.md` требует одного владельца факта. `UX.md` всё ещё говорит, что первая страница/точные маршруты не утверждены, тогда как `UX_PRODUCT_SHELL.md` и FRONTEND-001 уже фиксируют `/` как Chat | В первом разрешённом docs-package свести product behavior в `PRODUCT.md`, visual/responsive в `UX.md`; `UX_PRODUCT_SHELL.md` сократить до transitional note либо удалить после переноса фактов |
| **HIGH** | Staging UX v4 разросся до десятков взаимосвязанных документов и 48 changed paths | Это противоречит цели «минимальный достаточный контекст». `EXIT_GATE`, `GATE_REQUEST`, `GATE_STATUS`, `REVIEW_COORDINATION`, owner/reviewer indexes частично повторяют одно состояние | Заморозить создание новых coordination-docs. Консолидировать staging до 5–7 файлов: audit, decisions, implementation contract, lifecycle repair, traceability, archive/source |
| **HIGH** | Independent-review gate привязан к SHA, но не к реальной независимой личности | `review_evidence.py` проверяет только текстовый marker и SHA; он не подтверждает, что автор comment действительно reviewer и отличается от implementer | Усилить gate: проверять comment/review author, разрешённый reviewer identity и отсутствие совпадения с implementer; лучше использовать GitHub review APPROVE + exact commit binding |
| **HIGH** | `decides_next=true + next_package=null` создаёт реальный lifecycle deadlock | `validate_plan()` разрешает состояние, которое `transition()` затем не умеет продолжить; нет штатного recovery path, если сломан сам lifecycle tool | Исправить #188 отдельным control-plane repair. Одновременно формально определить break-glass recovery для отказа lifecycle tooling, а не изобретать его после следующей аварии |
| **HIGH** | FRONTEND-001 дошёл ровно до hard ceiling: 40 changed paths | Формально допустимо, но для UX shell это сильный сигнал чрезмерного scope. В одном PR смешаны shell, Account, Admin, Gallery, Studio, infra и docs | Следующие UI packages делать `tiny/normal`; не повторять cross-domain 40/40. Shared shell не должен тянуть доменные presentation-refactors без необходимости |
| **MEDIUM** | Метрика `45 user + 30 admin = 75/75` создаёт ложное ощущение готовности | PRODUCT прямо определяет реестр как target, а не как работающие страницы. Наличие записи/schema не доказывает UX depth, API contract или runtime | Использовать coverage только как «не забыли surface». Для готовности нужен статус CURRENT/PARTIAL/PLACEHOLDER/TARGET + API/test evidence; traceability matrix ближе к правильной метрике |
| **MEDIUM** | Полный UX package хранится как tar.xz, разбитый на Base64 parts | Для ~документационного пакета это недиффируемо, плохо ищется GitHub search, неудобно coding-agent и создаёт restore ceremony | Хранить модульные `.md/.json` напрямую в Git. Архив оставить максимум как release artifact/checksum, не как основной способ доступа |
| **MEDIUM** | `MASTER_SPEC_V4` и модульные документы дублируют друг друга | Большой master удобен человеку, но опасен как agent context и противоречит progressive disclosure | Не включать master в default routing. Для агента — только README/index + один feature module + exact owner/tests |
| **MEDIUM** | Future Video/Audio/3D UX описан глубже, чем подтверждён runtime | Даже с `PROPOSED` метками детальная timeline/DAW/scene модель может быть воспринята ботом как обязательная implementation spec | До реального domain package держать только product outcomes, states и resource constraints. Detailed editor UX писать после capability/data-contract |
| **MEDIUM** | Issue #189 смешивает решения «нужны сейчас» и дальние архитектурные решения | O-01/O-02/O-03 влияют на routes; O-04…O-08 относятся к будущим modality/data-model packages | Разделить immediate IA/routes от deferred architecture. Не блокировать FRONTEND-002 решениями о VideoProject/AudioProject/version graph |
| **LOW** | Owner visual acceptance требует решения по shell, в котором уже известен нежелательный `Инструменты` picker | Можно застрять в цикле «не принимаем baseline, потому что следующий package должен его исправить» | Либо explicit `ACCEPT baseline + follow_up`, либо короткий targeted patch до acceptance. Не создавать дополнительные доказательства без решения владельца |

## 1. Самая серьёзная проблема — shadow documentation

Мы сознательно называем `artifacts/ux-v4` non-canonical, но объём уже делает его практически альтернативной системой управления проектом. Там есть собственные decision register, route registry, file map, implementation contract, open decisions, gate status, repair scope, acceptance matrices и owner packets.

Формальная пометка «non-canonical» уменьшает риск, но не устраняет его. Coding-agent, получив ссылку на staging README, может прочитать его как более свежий и более подробный источник и проигнорировать repository-owned `PRODUCT/UX/ADMIN/ARCHITECTURE`.

**Вывод:** staging должен быть временным migration source, а не долговременным вторым knowledge base.

## 2. Canonical docs действительно противоречат друг другу

`DOCS_SYSTEM.md` говорит: пользовательское поведение принадлежит `PRODUCT.md`, visual/responsive/accessibility — `UX.md`, один факт имеет одного владельца.

При этом текущий `UX.md` всё ещё говорит, что точные маршруты и первая страница после входа не утверждены, а Chat-first — лишь допустимая концепция. Одновременно `UX_PRODUCT_SHELL.md` и фактический FRONTEND-001 уже фиксируют `/` как Chat home.

Это не косметика. Для агента это означает два правдоподобных ответа на вопрос «что является главным экраном?». Именно такие конфликты приводят к хаотическим правкам.

**Приоритет №1 после lifecycle gate — не новый дизайн, а canonical reconciliation.**

## 3. FRONTEND-001 структурно слишком широкий

PR #36 имеет ровно 40 changed files — максимальный `cross_domain` budget. Там одновременно меняются shell, Account presentation split, Admin presentation split, Gallery private preview, Image Studio split, CSS, Caddy CSP и документация.

По отдельности изменения могут быть корректными, но пакет слишком дорог для review и слишком сложен для причинно-следственной проверки. Hard ceiling не должен превращаться в целевой размер пакета.

Для будущих bot-friendly правок правильный масштаб — 5–15 файлов, один пользовательский результат и одна основная ownership boundary.

## 4. Safety architecture — сильная часть

Image path сохраняет серверную последовательность entitlement → quote → stable operation id → Job → Media. Unknown outcome не превращается в новую платную операцию. Jobs переживают навигацию. Private Media не подменяется provider URL. Unsupported Chat/Video/Audio/3D не выдаются за рабочий runtime.

Эти инварианты нельзя размыть ради более красивой верстки. Здесь текущая документация полезна: она правильно отделяет presentation от server truth.

## 5. Review gate технически можно подделать текстом

Текущий `review_evidence.py` ищет строку вида `INDEPENDENT_REVIEW PASS source=<sha> reviewer=<id>` в PR comments. Он не проверяет, что comment написал другой actor, что `reviewer=<id>` соответствует автору comment, что reviewer входит в разрешённый набор или что GitHub review действительно был APPROVE.

То есть gate хорошо защищает от **stale SHA**, но плохо защищает от **self-asserted independence**.

Для high-risk packages это нужно исправить до того, как механизм станет реальным governance control.

## 6. Issue #188 показывает архитектурный недостаток процесса

Проблема не только в одном `if plan.next_package != activate`. Более глубокий дефект: процесс предполагает, что control-plane всегда исправен, но не определяет безопасный recovery, если control-plane сам заблокировал продолжение.

Нужны два штатных пути:

- обычный `begin-next`;
- редкий, строго проверяемый break-glass recovery для ремонта lifecycle tooling, с owner approval, exact source, отдельным audit trail и без ослабления evidence.

Без второго пути следующая ошибка в state tooling снова создаст bootstrap paradox.

## 7. Coverage 75/75 нужно правильно интерпретировать

Это полезный completeness-check: ни одна заявленная surface не потеряна. Но это не означает, что 75 страниц «спроектированы одинаково глубоко» и тем более не означает readiness.

Нужны разные показатели:

- registry coverage;
- implementation status;
- API/data-contract readiness;
- state coverage;
- responsive/accessibility acceptance;
- runtime evidence.

Текущая `UX_V4_TRACEABILITY_MATRIX.md` уже ближе к этому подходу, чем простая цифра 75/75.

## 8. Что нужно прекратить делать

Не создавать новый документ на каждый уточняющий шаг. Не расширять UX v4 новыми будущими редакторами. Не добавлять новые route decisions до закрытия O-01…O-03. Не использовать staging как рабочую ветку product implementation. Не пытаться «идеально» документировать Video/Audio/3D до появления их runtime contracts.

## 9. Предлагаемая нормализация

Перед следующим product implementation staging следует свернуть до компактного набора:

1. `README.md` — index/status only.
2. `CRITICAL_ANALYSIS.md` — текущая оценка и долги.
3. `OWNER_DECISION_PACKET.md` + machine decision status.
4. `IMPLEMENTATION_CONTRACT.md` + current→target map/traceability, объединённые в один implementation handoff.
5. `ISSUE_188_REPAIR_SCOPE.md` + code/test spec, объединённые в один lifecycle repair handoff.
6. Исходный модульный UX spec — напрямую как diffable files; master/archive только human/reference artifact.

После переноса принятых фактов в canonical docs большинство промежуточных staging coordination files нужно удалить или переместить в history/review artifact.

## 10. Приоритет дальнейших действий

**P0:** исправить review identity weakness и lifecycle #188; закрыть human gates FRONTEND-001.

**P1:** canonical reconciliation `PRODUCT.md` + `UX.md`; убрать duplicate ownership с `UX_PRODUCT_SHELL.md`.

**P2:** выполнить маленький FRONTEND-002: удалить manual Chat `Инструменты`, исправить Help/navigation wording, добавить targeted tests/evidence.

**P3:** только после этого выбирать следующий реальный domain: Image editor/runtime expansion либо отдельная Video/Audio/3D capability package.

## Итоговый verdict

Проект сейчас **не страдает от недостатка контроля — он начинает страдать от избытка контроля и документационного ceremony**.

Сильная сторона — server-truth, paid-safety, ownership, exact-head evidence и fail-honest UI. Слабая — рост параллельных документов, слишком широкий FRONTEND-001 и не до конца согласованная canonical product/UX карта.

Следующий прирост качества даст не ещё один слой спецификаций, а **сокращение, консолидация и доведение одного маленького package до конца**.