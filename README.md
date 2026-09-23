# Career Quest

AI-навигатор развития сотрудников для HackAlem AI, трек Halyk Bank.

## Статус

React + Next.js + Tailwind для мобильного и настольного браузера, FastAPI,
PostgreSQL + SQLAlchemy, Alembic и Docker Compose.

- `/` — адаптивный экран сотрудника и пробное задание из трёх вопросов с объяснениями.
- Прогресс пробного задания сохраняется в localStorage текущего браузера. Можно продолжить
  прохождение после перезагрузки, посмотреть результат и пройти заново. Ответ фиксируется
  при переходе к следующему вопросу или результату.
- `/hr` — интерактивная HR-панель: шесть mock-профилей, поиск, фильтры, карта навыков,
  назначение обучения, оценка с обоснованием и CSV-экспорт. Состояние — в localStorage.
- Доменные модели и расчёт роста навыков реализованы на backend.

Бизнес-таблицы, первая миграция и транзакционный CLI-импорт датасета реализованы.
Вход/JWT, бизнес-API, добавочный импорт, scoring, OpenAI-объяснения и HR-аналитика — следующие этапы.
Пробное задание не связано с оценкой сотрудника и не отправляет результаты в БД.
HR-экран публичный и содержит только mock-данные. Авторизация и общая БД сотрудников
не подключены. Прогресс задания на `/` и данные HR пока независимы.

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
5. Нажмите «Начать задание». Устанавливать приложение на телефон не требуется.

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
Пробное задание и HR mock-демо работают без API; для проверки backend используйте `/api/v1/ready`.
Next.js читает `API_URL` только на сервере и проксирует `/api/v1/health` и `/api/v1/ready`.
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

Ручная проверка: открыть `/` на телефоне, пройти задание, перезагрузить страницу
после одного вопроса, продолжить, посмотреть результат и запустить повторно.
На `/hr` проверить фильтры, назначение обучения, оценку навыка, сохранение после
перезагрузки и CSV-экспорт. Тесты бота: из `apps/bot` запустить
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

## Структура

```text
apps/web/                 React + Next.js + Tailwind + TypeScript
apps/web/src/app/page.tsx  Мобильный веб-интерфейс сотрудника
apps/web/src/app/hr/       HR Dashboard
apps/api/app/api/          HTTP и Pydantic-контракты
apps/api/app/application/  Порты ранжирования и объяснений
apps/api/app/domain/       Модели и чистая логика навыков
apps/api/app/infrastructure/ SQLAlchemy и подключение к БД
apps/api/app/auth/         Роли и место для JWT-модуля
apps/api/migrations/      Alembic
apps/api/tests/           Pytest
```

Подробнее: [архитектура](docs/architecture.md), [этапы](docs/roadmap.md).
Работа команды: [распределение задач между тремя участниками](docs/team-tasks.md).
Результаты проверок и ограничения: [verification](docs/verification.md).
