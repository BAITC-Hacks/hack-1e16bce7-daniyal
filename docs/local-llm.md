# Локальная LLM на NVIDIA GPU

Страница `/recommendations` получает профили и текущие навыки из PostgreSQL,
подбирает до трёх мероприятий и запрашивает объяснения у модели. Ссылка есть на
главной странице. Существующая HR-панель `/hr` пока использует отдельные mock-данные.

Для L40S используется Ollama 0.34.3 и `qwen3:8b` (около 5.2 GB весов).
Ключ OpenAI не нужен. Нужны Docker Compose с поддержкой `gpus` и NVIDIA Container Toolkit.
API Ollama доступен только контейнерам, без опубликованного порта.

## Запуск

В корневом `.env` задайте:

```dotenv
LLM_PROVIDER=ollama
LLM_ENABLED=true
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT_SECONDS=90
WEB_BIND_HOST=127.0.0.1
API_BIND_HOST=127.0.0.1
```

```sh
docker compose --profile gpu up -d --wait ollama
docker compose exec ollama ollama pull qwen3:8b
docker compose --profile gpu up --build -d --wait
docker compose exec api alembic upgrade head
docker compose run --rm --no-deps -v "$PWD/dataset:/dataset:ro" api python -m app.import_dataset /dataset
```

Модель хранится в отдельном Docker volume и не скачивается при каждом запуске.
Настройки API применяются через `docker compose up -d api`, а не `restart`.
На удалённом сервере откройте web-порт 3000 через SSH-туннель/VS Code Ports.
Для текущей установки доступны `http://localhost:13000/recommendations` и API на 18000.
Туннель можно восстановить из локального WSL:

```sh
ssh -N -L 13000:127.0.0.1:3000 -L 18000:127.0.0.1:8000 vicarious-red-python
```

## Проверка

```sh
docker compose exec ollama ollama ps
curl -sS http://127.0.0.1:8000/api/v1/recommendations \
  -H 'Content-Type: application/json' -d '{"employee_id":"E0028","locale":"ru"}'
```

Успешный ответ содержит `explanation_source: "ollama"` и `fallback_reason: null`.
`ollama ps` должен показывать `100% GPU`. Первый запрос загружает модель в VRAM.
Таймаут/неверный ответ модели возвращает `template` с причиной, и интерфейс явно
сообщает об объяснениях по правилам. Одновременный запрос получает 429, пока модель занята.

Модель выбирает порядок и формулировки из проверенных фактов в JSON-плане.
Это ограниченная генерация объяснений, не свободный чат. Числа и рейтинг считает
детерминированный алгоритм. Пропуски, дубли и придуманные факты отклоняются.
Имена и ID сотрудников в запрос модели не отправляются. Текущие навыки читаются из БД
без повторного применения завершённых активностей. Язык объяснения: RU, KK или EN.

Эти маршруты предназначены для закрытой разработки через localhost/SSH. JWT и роли
ещё не реализованы; перед публичным доступом нужна авторизация бизнес-API.

Документация: [Ollama Docker](https://docs.ollama.com/docker),
[Chat API](https://docs.ollama.com/api/chat), [Qwen3 8B](https://ollama.com/library/qwen3:8b).

## Проверено на Brev, 2026-09-23

- L40S, Ollama 0.34.3, `qwen3:8b`, ID модели `500a1f067a9f`, `100% GPU`.
- 84 теста API пройдены; один отдельный PostgreSQL-тест пропущен без TEST_DATABASE_URL.
  Контексты и ранжирование из БД совпали с исходным датасетом для всех 200 сотрудников.
- Production-сборка Next.js и TypeScript прошли локально и на сервере.
- Настоящие запросы через web-прокси для RU/KK/EN вернули по три рекомендации
  с `explanation_source=ollama` и без fallback. Холодный запуск — 69 с,
  повторные запросы — 4–5 с; это замеры одного профиля, не гарантия задержки.
- Проверка в Chrome: 200 профилей, нажатие кнопки, три карточки, отметка AI,
  нет ошибок JavaScript. На ширине 390 px нет горизонтального переполнения.
