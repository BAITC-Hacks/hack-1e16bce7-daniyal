# Проверка каркаса — 23 сентября 2026

## Пройдено

- Pytest: 7 тестов, включая инварианты роста навыков и health/readiness.
- TypeScript обоих клиентов; production-сборка Next.js.
- Expo SDK 57: проверка совместимости зависимостей, экспорт iOS и Android bundles.
- Docker build API и web, Compose: все три сервиса healthy.
- API health, API readiness, readiness через Next.js: HTTP 200.
- HR-страница: HTTP 200; доступ к readiness с хоста: HTTP 200.
- Alembic current: подключение к PostgreSQL успешно, revisions пока нет.

Проверки JavaScript выполнены на Node 22.23.2, локальные Python-тесты — на Python 3.11,
контейнер API — на Python 3.12. PostgreSQL опубликован на localhost:55432,
поскольку Docker сообщал о конфликтах портов 5432 и 5433.

## Не проверено и известные ограничения

- Визуальная проверка страницы: подключённый браузер недоступен.
- Mobile на физическом устройстве и в запущенном симуляторе не проверен.
  Bundles собраны, но это не заменяет проверку сети и UI на устройстве.
- npm audit web: 0 уязвимостей. Для mobile: 10 moderate-сообщений в цепочке
  Expo tooling → xcode → uuid. Предлагаемый npm автоматический fix откатывает Expo
  на SDK 46; он не применён, чтобы сохранить совместимость SDK 57. Проверить обновление
  upstream перед публикацией приложения.
- Pytest выдаёт одно предупреждение deprecation внутри Starlette/AnyIO;
  тесты проходят.
