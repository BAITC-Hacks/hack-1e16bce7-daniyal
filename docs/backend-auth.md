# Демо-вход и API сотрудника

Backend поддерживает выбор синтетического профиля без пароля и отдельный вход HR
по общему демо-паролю. Роль назначает сервер, должность сотрудника не даёт прав HR.
Выбор профиля предназначен для хакатона, а не для проверки личности.
Таблица аккаунтов, регистрация, refresh token и серверный logout не используются.

## Настройка

По умолчанию `DEMO_AUTH_ENABLED=false`: маршруты `/auth/demo/*` возвращают 404,
защищённые маршруты — 401. Ранее выданные демо-токены также не принимаются.

В корневом `.env` для Compose или `apps/api/.env` для локального backend:

```dotenv
DEMO_AUTH_ENABLED=true
DEMO_HR_PASSWORD=<случайный пароль HR>
JWT_SECRET=<случайный секрет подписи минимум 32 байта>
```

Для каждого секрета можно отдельно запустить:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Секреты остаются на сервере; их не нужно помещать в frontend или Git.
При включённом демо-входе API откажется стартовать без обоих настроенных секретов.
Настройки читаются при запуске: после изменения перезапустите API.
JWT подписан HS256, действует 3600 секунд по часам сервера, issuer —
`career-quest-demo`, audience — `career-quest-api`. Смена JWT_SECRET отзывает все токены.
Смена HR-пароля действует на новые входы; уже выданные токены живут до истечения срока.

После установки зависимостей, миграции и импорта из README запустите API.
Для Compose: `docker compose up -d --build api`.
Новые таблицы этому этапу не нужны.

## Контракт для frontend

Префикс всех маршрутов — `/api/v1`. Данные и ошибки возвращаются с
`Cache-Control: no-store`. Оба входа принимают JSON, дополнительные поля отклоняются.

| Метод и путь | Тело / ответ |
| --- | --- |
| `GET /auth/demo/employees?limit=50&offset=0` | `{items, total, limit, offset}`; item: employee_id, full_name, role, grade |
| `POST /auth/demo/employee` | `{employee_id}` → `{access_token, token_type: "bearer", expires_in: 3600}` |
| `POST /auth/demo/hr` | `{password}` → такой же ответ с JWT роли HR |
| `GET /auth/me` | `{role: "employee" или "hr", employee_id: string или null}` |
| `GET /employees/{id}` | employee_id, full_name, role, grade, department, manager_id, hire_date, tenure_months, work_format, preferred_language, career_goal, last_review_date |
| `GET /employees/{id}/skills` | `{employee_id, items}`; item: skill_id, name, type, category, description, assessed_level, level |
| `GET /employees/{id}/activities?limit=50&offset=0` | `{items, total, limit, offset}`; item: исходные поля activity_history.csv плюс event_title и event_type |

`role` в профиле/списке — должность из датасета; `role` в `/auth/me` — право доступа.
`career_goal` — `{target_role, target_grade}` или null; даты — ISO `YYYY-MM-DD`.
История сохраняет статусы completed, in_progress, dropped, no_show, declined, overdue.
`assessed_level` — последняя оценка, `level` — сохранённый текущий уровень.
API чтения не начисляет навыки повторно и не возвращает внутреннее `effects_applied`.

Список профилей открыт только при включённом демо-режиме. Все остальные GET-маршруты
требуют `Authorization: Bearer <access_token>`. Сотрудник читает только свой ID;
HR может открыть любой профиль. Сотрудник с должностью HR Business Partner
по-прежнему получает только роль employee через вход сотрудника.

Пагинация: limit 1–100 (по умолчанию 50), offset ≥ 0. Список сотрудников сортируется
по employee_id, навыки — по skill_id, история — по date DESC, record_id DESC.
Пустые коллекции возвращаются с HTTP 200, items=[]; total отражает полный размер.

Ошибки `{detail: string}`: 401 — неверный пароль/токен или нет авторизации;
403 — чужой профиль для сотрудника; 404 — отсутствующий профиль или выключенный
демо-вход; 503 — недоступна БД. Ошибки валидации 422 содержат detail как массив
с loc/msg/type, без отражения присланных секретов. Проверка чужого ID предшествует
поиску записи. Недействительный/удалённый субъект JWT получает 401.

## Примеры

```sh
curl 'http://localhost:8000/api/v1/auth/demo/employees?limit=50'
curl -X POST http://localhost:8000/api/v1/auth/demo/employee \
  -H 'Content-Type: application/json' -d '{"employee_id":"E0001"}'
curl -X POST http://localhost:8000/api/v1/auth/demo/hr \
  -H 'Content-Type: application/json' -d '{"password":"<пароль из .env>"}'
curl http://localhost:8000/api/v1/auth/me -H 'Authorization: Bearer <access_token>'
curl http://localhost:8000/api/v1/employees/E0001/skills -H 'Authorization: Bearer <access_token>'
curl http://localhost:8000/api/v1/employees/E0001/activities -H 'Authorization: Bearer <access_token>'
```

Интерактивная схема: `/docs`. Для защищённых запросов вставьте access_token в Authorize.

## Вход через сайт

На http://localhost:3000 доступны кнопки «Сотрудник» и «HR». Сотрудник выбирает
профиль из подсказок или вводит ID, например E0001. HR вводит DEMO_HR_PASSWORD
из корневого `.env`. После входа открывается соответствующий кабинет.
Web-прокси хранит JWT в HttpOnly cookie, проверяет Origin POST-запросов, получает
личность через auth/me и передаёт Bearer только серверу API. Кнопка «Выйти» удаляет cookie.
Список демо-профилей доступен через web-прокси без сессии только при включённом демо-входе.

Frontend адаптирован к backend-ответам профиля, навыков и истории. Траектория,
рекомендации, completion и HR-аналитика ещё не реализованы на backend; соответствующие
секции пока показывают ошибки доступности. Это не ошибка входа.
