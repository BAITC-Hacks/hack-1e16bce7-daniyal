# Frontend: экраны и контракт интеграции

Реализованы UI для задач 1.1–1.12 из `team-tasks.md`, demo-вход и web-прокси.
На `/` — профиль сотрудника; на `/hr` — аналитика, сотрудники, просмотр профиля
и импорт. Расчёты readiness, scoring, gain и выбор рекомендаций в браузере отсутствуют.
Старые localStorage-демо и ручная оценка навыков удалены.

**Статус интеграции:** профиль, траектория, рекомендации, каталог, completion,
HR-аналитика и импорт подключены к FastAPI. Подробности актуального сквозного
сценария, дополнительных query-параметров и метрик — в
[career-workspace.md](career-workspace.md). Production UI не подставляет фикстуры.
При 404 отсутствующего маршрута появляется сообщение о разработке; действующие
маршруты запрашиваются без предварительной блокировки.

## HTTP

Все пути относительны `/api/v1`. UI-модели определены в
[`contracts.ts`](../apps/web/src/lib/contracts.ts); адаптер существующих read-контрактов —
[`api.ts`](../apps/web/src/lib/api.ts). Для ещё не реализованных API списки предложены
как JSON-массивы; профиль, траектория и результаты действий — объекты.
Пустые списки допустимы. `null` readiness означает отсутствие расчёта, а не 0%.
Readiness измеряется в процентах 0–100; уровни навыков — 0–5.

| Метод, путь | Запрос / ответ |
| --- | --- |
| POST `auth/demo/employee` | `{employee_id}` → FastAPI `{access_token, token_type, expires_in}`; web возвращает `{user}` |
| POST `auth/demo/hr` | `{password}` → такой же ответ; web проверяет выданный JWT через auth/me |
| GET `auth/me` | FastAPI `{role, employee_id}`; web оборачивает в `{user}` |
| POST `auth/logout` | Только Next.js: удаляет cookie, → `{ok: true}` |
| GET `employees/{id}` | Реальный EmployeeProfile: ID, full_name, role, grade, tenure_months, department, career_goal и др.; readiness пока только из trajectory |
| GET `employees/{id}/skills` | Реальный `{employee_id, items: SkillResponse[]}`; level → current_level, required_level=null; требования отдельно из trajectory |
| GET `employees/{id}/trajectory` | `Trajectory`: current_grade, target_grade/target_role (nullable), упорядоченный grades[], career_readiness, requirements: Skill[] |
| POST `employees/{id}/recommendations` | `{language: "ru"}` → `Recommendation[]`, 0–3, в порядке Python engine |
| GET `events/{id}` | `Event`: event_id, title, description, type, duration_hours (optional/nullable), develops_skills[] |
| GET `employees/{id}/activities?limit=50&offset=0` | Реальный `{items, total, limit, offset}`; event_title → title; кнопки страниц в UI |
| POST `employees/{id}/activities/{event_id}/complete` | `{}` → `Completion` с before/after, already_completed и changes[] |
| GET `hr/dashboard` | `Dashboard`: employee_count, average_readiness, without_recommendations, completed_activities, active_this_month, as_of_date |
| GET `hr/skill-gaps` | `SkillGap[]`: skill_id, name, employee_count |
| GET `hr/employees?include_readiness=true` | `Employee[]`, полный разрешённый список; поиск/фильтры UI по этому списку |
| GET `hr/activity-stats` | `ActivityStat[]`: event_id, title, participant_count, statuses (все 6 ключей, включая нули) |
| GET `hr/recommendation-coverage` | `Employee[]` только сотрудников без рекомендованного шага |
| POST `datasets/import` | multipart (см. ниже) → `ImportResult` |

Метрики по всей истории загруженного набора на `as_of_date`. `completed_activities` —
число завершённых **участий**; participant_count — число уникальных участников события;
statuses — число записей участия по статусам. Средняя readiness рассчитывается сервером
по сотрудникам, для которых есть следующий грейд и расчёт. При отсутствии таких
сотрудников — null. KPI «Активны в этом месяце» и распределение статусов реализованы; определения описаны в career-workspace.md.

Статусы импортированной истории и аналитики: completed, in_progress, dropped,
no_show, declined, overdue. Устаревшие missed/registered не используются; схема соответствует разделу 1.6 задач.
Последовательность грейдов целиком приходит в `grades`, не зашита в UI.

### Рекомендация

```json
{
  "event_id": "EV_014",
  "title": "System Design Workshop",
  "priority": 1,
  "score": 0.87,
  "skills": [{
    "skill_id": "SK_SYSTEM_DESIGN", "name": "System Design",
    "current_level": 2, "required_level": 4, "gain": 1, "predicted_level": 3
  }],
  "career_readiness_before": 68,
  "career_readiness_after": 76,
  "reason": "Объяснение с учётом грейда, требований, разрывов и истории.",
  "explanation_source": "fallback"
}
```

Числа — иллюстрация. explanation_source: ai/fallback. `gain` — заявленный эффект
мероприятия; predicted_level — фактический прогноз с ограничением max_level.
Детали Event.develops_skills содержат skill_id, name, gain и max_level.
UI показывает прогноз до выполнения, не начисляет его самостоятельно.

### Завершение

```json
{
  "event_id": "EV_014", "already_completed": false,
  "changes": [{"skill_id": "SK_SYSTEM_DESIGN", "name": "System Design", "before": 2, "after": 3}],
  "career_readiness_before": 68, "career_readiness_after": 76
}
```

Во время запроса кнопка и закрытие диалога заблокированы. После успеха UI показывает
результат и заново запрашивает профиль, траекторию, навыки, историю и рекомендации.
Ошибка завершения оставляет профиль неизменным. Если сохранение успешно, а обновление
данных не удалось, сообщение об успехе остаётся, соответствующая секция показывает
ошибку с повтором запроса. Уже учтённое выполнение не должно давать повторный gain.

Completion требует Idempotency-Key; UI сохраняет ключ при повторе запроса. Для
повторяемых активностей выбирается record_id или session_date по контракту backend.
Демо-завершение будущей сессии явно обозначено в диалоге.
HR-профиль доступен только для чтения, без кнопки завершения.

### Импорт

multipart поля:

- `mode=initial`: employees.json, events.json, skills.json, activity_history.csv.
- `mode=append`: employees.json, activity_history.csv; существующий справочник/события.

Имена multipart-полей совпадают с именами файлов. JSON сохраняет исходную обёртку
meta/employees, meta/events или meta/skills/role_profiles — фронтенд её не преобразует.
UI проверяет наличие, лимит 10 МБ на файл и синтаксис JSON; семантика, CSV, ссылки
и атомарность — серверная валидация. Backend должен отдельно ограничивать размер загрузки.
Режим append реализован с атомарной проверкой связей и идемпотентностью пакета.

```json
{"status":"imported","employees":200,"events":40,"skills":60,"history_records":2743}
```

`status=unchanged` означает идемпотентный повтор. Числа — результат операции,
для unchanged — числа ранее импортированного набора. Ответ 422 поддерживает стандартный
FastAPI `detail: [{loc: [...], msg: "..."}]`, включая номер CSV-строки в loc/msg.
Другие ошибки: detail-строка, 401 (новый вход), 403 (нет доступа), 404, 409, 5xx.

## Сессия и прокси

Next.js хранит JWT в HttpOnly, SameSite=Lax cookie `cq_session`, Secure при HTTPS.
Браузер получает только user; JWT не попадает в localStorage или JS-ответ входа. Роль берётся из auth/me после выдачи токена, а не из формы входа.
Перезагрузка восстанавливает сессию через auth/me. 401 очищает cookie и возвращает UI
к входу. Web-прокси использует allowlist путей/методов, передаёт JWT как Bearer,
не следует редиректам upstream и проверяет Origin на POST. API_URL — только серверная
настройка. Кэширование запрещено. Таймаут upstream: 12 секунд, импорт: 55 секунд.
Клиентский таймаут: 15/60 секунд. Никаких секретов OpenAI/JWT на фронтенде.

Cookie и скрытие HR-экрана не заменяют проверку прав backend. Demo-вход допускает
выбор роли лишь в специальной серверной demo-конфигурации, не для production-доступа.

## Проверки

Из `apps/web`:

```sh
npm run typecheck
npm run build
# Если Turbopack не может открыть служебный порт в ограниченном окружении:
# npm run build -- --webpack
npm test
```

`npm test` запускает production Next.js и тестовый HTTP API на 127.0.0.1:18002/18001.
Проверяет маршруты, cookie/Origin, передачу авторизации, completion, импорт,
валидацию и недоступность upstream. Это проверка прокси на fixture API, а не
проверка транзакций, прав или расчётов FastAPI.

Для ручной проверки UI на фиксированных тестовых ответах (два терминала):

```sh
node tests/fixture-api.mjs
API_URL=http://127.0.0.1:18001 npm run dev -- --port 18002
```

Использовать любой ID, например JURY-42; `missing` возвращает 404 при входе.
Пароль HR исключительно для fixture API: `fixture-hr`; реальный пароль задаётся на backend.
Fixture находится только в tests, импортируется исключительно тестами и не
является production fallback. После запуска доступны оба режима demo-входа.
Полный сценарий с настоящим FastAPI и SQLite проверяется test_career_api.py.
