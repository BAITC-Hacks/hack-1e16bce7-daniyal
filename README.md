# Career Quest

AI-навигатор развития сотрудников для HackAlem AI, трек Halyk Bank.

## Статус

React + Next.js + Tailwind для мобильного и настольного браузера, FastAPI,
PostgreSQL + SQLAlchemy, Alembic и Docker Compose.

- `/` — экраны профиля, карьерной траектории, навыков, рекомендаций,
  деталей активности, завершения с результатом и истории участия.
- `/hr` — экраны KPI, gaps, статистики активностей, сотрудников с поиском/фильтрами,
  просмотра профиля и загрузки исходного/добавочного датасета.
- Demo-вход, HttpOnly-сессия, allowlist web-прокси; загрузка, пустые состояния,
  ошибки и повтор запросов. В браузере нет расчётов scoring/readiness или локальной БД.
- Доменные модели, расчёт роста навыков и автономный AI-слой: gaps/readiness,
  рекомендации, OpenAI-объяснения и fallback на трёх языках.

Бизнес-таблицы, первая миграция и транзакционный CLI-импорт датасета реализованы.
**Фронтенд подключён к текущим контрактам входа, профиля, навыков и истории.**
На странице входа выберите «Сотрудник» и профиль (например E0001), либо «HR»
и введите `DEMO_HR_PASSWORD` из локального `.env`. Траектория,
completion, HTTP-импорт, рекомендации, объяснения и HR-аналитика ещё ожидают API.
Автономный AI-слой готов; его подключение к HTTP API — следующий этап.
Неготовые секции показывают ошибку с повтором; mock-данные не подставляются.
Контракт и тестовый режим: [Frontend API](docs/frontend-api.md).

Telegram-бот: [запуск и команды](apps/bot/README.md). Отдельный mock JSON, напоминания
о дедлайнах, просрочках и отсутствии участия. Токен нужен только для реальной отправки.

## Быстрый запуск

Нужен запущенный Docker Desktop / Docker Engine с Compose:

```sh
cp .env.example .env
docker compose up --build -d --wait
```

В PowerShell вместо `cp` можно использовать `Copy-Item .env.example .env`.

- Приложение сотрудника: http://localhost:3000
- HR Dashboard: http://localhost:3000/hr
- OpenAPI: http://localhost:8000/docs
- API: http://localhost:8000/api/v1/health
- Готовность API + PostgreSQL: http://localhost:8000/api/v1/ready

Ключ OpenAI не нужен. Первый запуск скачивает зависимости и образы.
Web по умолчанию доступен в локальной сети (`WEB_BIND_HOST=0.0.0.0`).
API и PostgreSQL доступны только на localhost; браузер обращается к API через web-прокси.
PostgreSQL использует порт `55432` (`POSTGRES_PORT`) и сохраняет данные в Docker volume.
`docker compose down` останавливает стек без удаления данных.
Локальные credentials из `.env.example` предназначены для разработки.
При изменении credentials обновите также локальный `DATABASE_URL`; для пароля в URL
нужно percent-encoding специальных символов. В уже созданной БД переменные Compose
не меняют пароль автоматически.

## Открыть с телефона

1. Подключите компьютер и телефон к одной Wi-Fi сети.
2. Запустите приложение командой выше. Если `.env` уже существует, убедитесь,
   что `WEB_BIND_HOST=0.0.0.0`, и выполните `docker compose up -d web`.
3. Узнайте локальный IPv4 компьютера (`ipconfig` в Windows, адрес адаптера Wi-Fi).
4. Откройте в браузере телефона `http://<IP-компьютера>:3000`, например `http://192.168.1.10:3000`.
5. Войдите с demo-ролью после настройки демо-доступа (см. ниже). Устанавливать приложение не требуется.

Если страница не открывается, проверьте доступ к TCP-порту 3000 в брандмауэре
для частной сети и отсутствие изоляции устройств в Wi-Fi.
`localhost` на телефоне означает сам телефон. Для доступа через интернет нужен
отдельный деплой с публичным HTTPS-адресом; текущая настройка рассчитана на локальную сеть.

## Локальная разработка

Нужен Node.js 22.13+ ветки 22 LTS (`nvm install && nvm use` в корне).

```sh
cd apps/web
cp .env.example .env.local
npm ci
npm run dev
```

Сервер слушает `0.0.0.0:3000`: с телефона используйте тот же адрес компьютера.
Для проверки backend используйте `/api/v1/ready`. Для проверки UI до готовности бизнес-API
есть отдельный [тестовый режим](docs/frontend-api.md#проверки).
Next.js читает `API_URL` только на сервере и проксирует разрешённые system- и бизнес-маршруты.
Браузеру не нужен отдельный адрес API или настройка CORS.

Для локального backend оставьте PostgreSQL в Docker, остановив контейнеры API/web:

```sh
docker compose stop api web
docker compose up -d --wait db
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/api/requirements-dev.txt
cd apps/api
cp .env.example .env
../../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1
```

Нужен Python 3.11+. В Windows используйте `.venv\Scripts\python.exe`
вместо `.venv/bin/python` (из `apps/api` — `..\..\.venv\Scripts\python.exe`).

## Проверки

Из корня:

```sh
.venv/bin/python -m pytest -c apps/api/pytest.ini apps/api/tests -q
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
docker compose config --quiet
```

Ручная проверка: после настройки демо-доступа и импорта датасета войти как сотрудник,
проверить профиль, навыки и историю; затем проверить вход HR и выход из сессии.
Для секций без backend API проверить сообщения об ошибках и повтор запросов.
Тестовый режим UI описан в [Frontend API](docs/frontend-api.md#проверки).
Тесты бота: из `apps/bot` запустить
`python -m unittest discover -s tests -v`.

## Миграции

Первая миграция `0001_dataset` создаёт бизнес-таблицы. Из `apps/api`:

```sh
../../.venv/bin/alembic upgrade head
../../.venv/bin/python -m app.import_dataset ../../dataset --validate-only
../../.venv/bin/python -m app.import_dataset ../../dataset
```

Импорт принимает исходные `skills.json`, `employees.json`, `events.json` и
`activity_history.csv`. Операция атомарна; повтор того же набора возвращает
`unchanged`, изменённый набор отклоняется без перезаписи прогресса.
`--validate-only` не требует БД. Подробные правила и ограничения:
[данные backend](docs/backend-data.md).

В Docker после пересборки API:

```sh
docker compose up -d --build api
docker compose exec api alembic upgrade head
docker compose cp dataset api:/tmp/career-quest-dataset
docker compose exec api python -m app.import_dataset /tmp/career-quest-dataset
```

Миграции и импорт применяются явно, а не при каждом старте API.

## Демо-вход и API сотрудника

Backend поддерживает выбор сотрудника из датасета и вход HR по одному демо-паролю.
Включается явно через `DEMO_AUTH_ENABLED=true`, `DEMO_HR_PASSWORD` и `JWT_SECRET`.
Настройка, контракты и curl-примеры: [backend-auth](docs/backend-auth.md).
Frontend использует эти контракты для входа, профиля, навыков и истории.

## Структура

```text
apps/web/                 React + Next.js + Tailwind + TypeScript
apps/web/src/app/page.tsx  Мобильный веб-интерфейс сотрудника
apps/web/src/app/hr/       HR Dashboard
apps/api/app/api/          HTTP и Pydantic-контракты
apps/api/app/application/  Порты ранжирования и объяснений
apps/api/app/domain/       Модели и чистая логика навыков
apps/api/app/infrastructure/ SQLAlchemy и подключение к БД
apps/api/app/auth/         Роли и JWT демо-входа
apps/api/migrations/      Alembic
apps/api/tests/           Pytest
```

Подробнее: [архитектура](docs/architecture.md), [этапы](docs/roadmap.md).
Работа команды: [распределение задач между тремя участниками](docs/team-tasks.md).
Результаты проверок и ограничения: [verification](docs/verification.md).
AI-модуль, автономное демо и контракт для backend: [интеграция AI](docs/ai-integration.md).
