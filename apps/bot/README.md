# Career Quest Telegram bot

Отдельный Python 3.11+ worker без сторонних зависимостей. Отправляет напоминания
через Telegram Bot API, принимает команды через long polling.
Основной FastAPI и frontend не меняет. Источник сейчас — отдельный **mock JSON**,
а не данные localStorage из HR-панели. Это запускаемый прототип, не production-интеграция.

## Проверка без токена и сети

Из `apps/bot`:

```sh
python -m career_bot init-demo
python -m career_bot preview
python -m unittest discover -s tests -v
```

`init-demo` создаёт `data/employees.json` с актуальными относительно запуска датами.
Существующий файл не перезаписывается; для нового примера укажите `--data data/new-demo.json`.
`preview` показывает потенциальные сообщения, в том числе вне часов отправки.
Он не обращается к Telegram и не меняет историю доставки.

## Реальный бот

1. Создайте отдельного бота через [BotFather](https://t.me/BotFather).
2. Скопируйте `.env.example` в `.env` (`Copy-Item .env.example .env` в PowerShell).
3. Впишите `TELEGRAM_BOT_TOKEN` и `TELEGRAM_BOT_USERNAME` в локальный `.env`.
   Токен никогда не помещается в браузер, git или логи.
4. В одном терминале запустите `python -m career_bot run`.
5. В другом выполните `python -m career_bot invite --employee arman`.
6. Передайте одноразовую ссылку только владельцу этого профиля. Он открывает её
   и нажимает Start. После этого worker сможет отправлять ему напоминания.

Ссылка действует 15 минут; повторная выдача отменяет предыдущую. Привязка принимается
только из личного чата. Обычный `/start arman` не позволяет получить чужой профиль.
Уже привязанный профиль нельзя перепривязать без `/stop` в исходном чате.
Потеря доступа к исходному чату требует администраторского обслуживания SQLite;
самостоятельное восстановление аккаунта в прототип не входит.

`/help` — справка, `/status` — статус подписки, `/pause` — пауза,
`/resume` — продолжение, `/stop` — отвязка и прекращение сообщений.
Блокировка бота пользователем приостанавливает подписку при следующем ответе 403.

## Правила уведомлений

- Отсутствие участия 14 дней (порог `INACTIVE_DAYS`): напоминание раз в 7 дней,
  отсчёт от последнего участия; без истории — от даты присоединения.
- Дедлайн менее чем через 24 часа: однократно на срок задания.
- Просрочка: не чаще раза в календарный день (UTC+5).
- Завершённое задание не создаёт напоминания.
- Автоматическая отправка только 09:00–20:00 UTC+5. Команды доступны всегда.
- До 5 напоминаний в одном сообщении, не больше одного дайджеста в час сотруднику.
  Большое число заданий распределяется по следующим часовым проверкам.

Ссылка «Открыть Career Quest» добавляется только при заданном `CAREER_QUEST_URL`.
Нужен доступный с телефона HTTPS-адрес; localhost компьютера для телефона не подходит.

## Формат данных и хранение

```json
{
  "version": 1,
  "employees": [{
    "id": "arman",
    "joined_at": "2026-07-01T00:00:00+05:00",
    "last_participation": "2026-09-01T12:00:00+05:00",
    "tasks": [{
      "id": "architecture",
      "title": "Защита архитектуры",
      "due_at": "2026-09-25T18:00:00+05:00",
      "completed": false
    }]
  }]
}
```

Все даты должны содержать timezone. `last_participation` допускает `null`.
JSON перечитывается каждый цикл: меняйте `completed`, срок и участие в этом файле.
При ошибке файла рассылка останавливается до исправления, старые данные не используются.
SQLite `data/bot.sqlite3` сохраняет привязки, паузы, offset обновлений и успешные доставки.
Оба файла игнорируются git. Сделайте резервную копию перед переносом worker.

Запускайте **один worker на один Telegram-бот и файл SQLite**. Несколько экземпляров
не поддерживаются. При 409 (конфликт polling/webhook) процесс завершается, а не удаляет webhook.
При 429 используется `retry_after`. Ошибка доставки одному пользователю не блокирует других;
401 завершает процесс для исправления токена. Успешные отправки не повторяются после рестарта.
Но Telegram `sendMessage` не поддерживает ключ идемпотентности: при сетевом таймауте
после фактической отправки или аварии до записи SQLite возможен повтор. Exactly-once не обещается.

## Архитектура и следующий этап

`domain.py` — чистые правила; `service.py` — сценарии и порты;
`adapters.py` — JSON, SQLite и Telegram; `__main__.py` — CLI и цикл запуска.
Тесты работают с временной SQLite и fake sender, не отправляют реальные сообщения.

Для подключения к настоящему Career Quest нужно заменить JSON-адаптер данными backend,
добавить дедлайны и attendance в общую БД, выдавать invite только после авторизации сотрудника.
Для работы при выключенном ноутбуке worker нужно развернуть на постоянно работающем сервере.
AI не нужен для определения дедлайнов или отсутствия участия.

## Docker (если Python не установлен)

Из `apps/bot`, после заполнения `.env`:

```sh
docker build -t career-quest-bot .
docker volume create career_quest_bot_data
docker run --rm -v career_quest_bot_data:/app/data career-quest-bot init-demo
docker run --rm -v career_quest_bot_data:/app/data career-quest-bot preview
docker run --rm --env-file .env -v career_quest_bot_data:/app/data career-quest-bot invite --employee arman
docker run -d --name career-quest-bot --restart unless-stopped --env-file .env -v career_quest_bot_data:/app/data career-quest-bot run
```

Состояние сохраняется в volume. `docker stop career-quest-bot` останавливает рассылку.
Docker-образ описан, но его сборка требует доступного Docker и сети.

Официальные контракты: [getUpdates](https://core.telegram.org/bots/api#getupdates),
[sendMessage](https://core.telegram.org/bots/api#sendmessage),
[deep linking](https://core.telegram.org/bots/features#deep-linking).
