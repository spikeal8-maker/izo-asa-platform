# Состояние

Этап: Foundation 0, первый PR. Не готово для публичного развёртывания.

Локально выполненные и GitHub-проверки публикуются отдельно в описании PR с SHA.
Наличие workflow не означает, что он выполнялся. Авторизация и генерация отсутствуют.

Пока не закрыты:
- generated dependency locks после первого разрешения пакетов на GitHub;
- проверка Docker Compose и настоящая browser-сборка в CI;
- фиксация container base images по digest перед выпуском;
- branch protection / required checks (CODEOWNERS сам по себе не защита);
- финальная ограничительная лицензия и проверка лицензий зависимостей;
- production HTTPS, secret files/manager, backup restore rehearsal и access control;
- реальные Telegram/MAX SDK и signed auth, не эмуляция;
- durable worker, auth, ledger и продуктовые функции из NEXT.

Первый workflow допускает bootstrap отсутствующих dependency locks и выводит только
их сжатое содержимое, не secrets. Перед принятием основания locks надо закоммитить
и убрать bootstrap-fallback. В обычной работе разрешены только locked installs.
