# Career Quest

AI-навигатор развития сотрудников для HackAlem AI, трек Halyk Bank.

## Статус

Запускаемый каркас: Expo + React Native, Next.js + Tailwind, FastAPI,
PostgreSQL + SQLAlchemy, Alembic, Pytest и Docker Compose.
Мобильный клиент проверяет готовность API и БД. Есть доменные модели и расчёт роста навыков.
Импорт, бизнес-таблицы, вход/JWT, scoring, OpenAI-объяснения и HR-аналитика — следующие этапы.
HR-экран — интерактивное frontend-демо с шестью mock-профилями, поиском, фильтрами,
картой навыков, назначением обучения, оценками и CSV-экспортом. Состояние сохраняется
в localStorage браузера; авторизация и общая БД сотрудников не подключены.

Telegram-бот напоминаний: [запуск и команды](apps/bot/README.md). Бот работает
с отдельным mock JSON: дедлайны, просрочки, отсутствие участия, пауза и отписка.
Токен требуется только для реальной отправки; `preview` и тесты работают без сети.

## Быстрый запуск

Нужен запущенный Docker Desktop / Docker Engine с Compose:

```sh
cp .env.example .env
docker compose up --build -d --wait
```

- HR Dashboard: http://localhost:3000
- OpenAPI: http://localhost:8000/docs
- API: http://localhost:8000/api/v1/health
- Готовность API + PostgreSQL: http://localhost:8000/api/v1/ready

Ключ OpenAI не нужен. Первый запуск скачивает зависимости и образы.
PostgreSQL доступен на `localhost:55432` (настраивается через `POSTGRES_PORT`).
По умолчанию порты доступны только на localhost. БД сохраняется в Docker volume.
`docker compose down` останавливает стек без удаления данных.
Локальные credentials из `.env.example` предназначены для разработки.
При изменении credentials обновите также локальный `DATABASE_URL`; для пароля в URL
нужно percent-encoding специальных символов. В уже созданной БД переменные Compose
не меняют пароль автоматически.

## Mobile

Используйте Node.js 22.13+ ветки 22 LTS (`nvm install && nvm use` в корне).
Приложение запускается отдельно от Docker:

```sh
cd apps/mobile
cp .env.example .env
npm ci
npm start
```

Нужен Expo Go, совместимый с SDK 57, либо development build.
Для iOS Simulator используйте `EXPO_PUBLIC_API_URL=http://127.0.0.1:8000`;
для Android Emulator — `http://10.0.2.2:8000`.

Для физического телефона:

1. Подключите компьютер и телефон к одной доверенной Wi-Fi сети.
2. Установите `API_BIND_HOST=0.0.0.0` в корневом `.env` и выполните
   `docker compose up -d --wait api web` из корня.
3. В `apps/mobile/.env` укажите `EXPO_PUBLIC_API_URL=http://<LAN-IP-компьютера>:8000`.
4. Откройте этот адрес с `/api/v1/ready` в браузере телефона: ожидается `ready`.
5. Перезапустите Expo (`npm start`) и сканируйте QR-код. Разрешите доступ к локальной сети.

`localhost` на телефоне обозначает сам телефон. Tunnel Expo не публикует API:
телефону всё равно нужен доступ к backend. Публичные переменные Expo включаются в bundle;
секреты и ключ OpenAI там хранить нельзя.

## Локальная разработка без контейнеров приложений

Оставьте PostgreSQL в Docker, остановив ранее запущенные API/web:

```sh
docker compose stop api web
docker compose up -d --wait db
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/api/requirements-dev.txt
cd apps/api
cp .env.example .env
../../.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0
```

Нужен Python 3.11+. Для desktop-only разработки можно использовать `--host 127.0.0.1`.
В другом терминале:

```sh
cd apps/web
cp .env.example .env.local
npm ci
npm run dev
```

Next.js читает `API_URL` только на сервере и проксирует проверки `/api/v1/health`
и `/api/v1/ready`; браузеру не нужен CORS. Native Expo обращается прямо к API.
Expo Web пока не настроен.

## Проверки

Из корня:

```sh
.venv/bin/python -m pytest -c apps/api/pytest.ini apps/api/tests -q
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npm --prefix apps/mobile run typecheck
```

Из `apps/mobile`: `npx expo install --check` для совместимости зависимостей,
`npx expo export --platform all` для проверки bundles iOS/Android без устройства.

Проверка контейнеров:

```sh
docker compose config --quiet
docker compose ps
curl -f http://localhost:8000/api/v1/ready
curl -f http://localhost:3000/api/v1/ready
```

## Миграции

Alembic настроен, но бизнес-таблиц и revisions пока нет.
Из `apps/api` можно проверить подключение: `../../.venv/bin/alembic current`.
Будущие SQLAlchemy-модели регистрируются в `Base.metadata` и импортируются в `migrations/env.py`:

```sh
../../.venv/bin/alembic revision --autogenerate -m "add domain tables"
# Проверить сгенерированный файл перед применением.
../../.venv/bin/alembic upgrade head
```

В Docker: `docker compose exec api alembic upgrade head`.
Миграции применяются явно, а не при каждом старте API.

## Структура

```text
apps/mobile/           Expo + React Native + TypeScript
apps/web/              Next.js App Router + Tailwind + TypeScript
apps/api/app/api/      HTTP и Pydantic-контракты
apps/api/app/application/  порты ранжирования и объяснений
apps/api/app/domain/   модели и чистая логика навыков
apps/api/app/infrastructure/  SQLAlchemy и подключение к БД
apps/api/app/auth/     роли и место для JWT-модуля
apps/api/migrations/   Alembic
apps/api/tests/        Pytest
```

Подробнее: [архитектура](docs/architecture.md), [этапы](docs/roadmap.md).

Результаты проверок и ограничения: [verification](docs/verification.md).
