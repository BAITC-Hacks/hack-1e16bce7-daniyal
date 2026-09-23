# AI-слой: запуск и подключение к backend

Реализованы Python engine, расчёт gaps/readiness, симуляция через существующий
`apply_skill_effects`, адаптер OpenAI и локальные объяснения RU/KK/EN.
Модуль работает без БД и HTTP-сервера. Backend подключает его к своим данным,
авторизации и транзакциям. Frontend пока не вызывает этот модуль.

## Быстрая проверка

Из корня, PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r apps/api/requirements-dev.txt
Set-Location apps/api
../../.venv/Scripts/python.exe -m app.ai_demo --employee E0028 --locale ru
```

Linux/macOS: используйте `.venv/bin/python` вместо `.venv/Scripts/python.exe`.
Рекомендуется Python 3.11+; локальная проверка также прошла на Python 3.10.3.
Демо по умолчанию **не обращается к сети**, даже если задан ключ. Можно указать
`--dataset /path/to/dataset`, любой `--employee` из этого набора и `--locale ru|kk|en`.
Без `--locale` используется язык профиля. Вывод — JSON с фактами и объяснениями.

Для настоящего запроса создайте `apps/api/.env` из `.env.example` и локально заполните
`OPENAI_API_KEY`. Ключ не добавлять в Git или переменные `NEXT_PUBLIC_*`.

```powershell
# Из apps/api, после настройки .env:
../../.venv/Scripts/python.exe -m app.ai_demo --employee E0028 --locale ru --live
```

Проверяйте `explanation_source: "openai"`. При fallback live-команда завершится с кодом 2,
хотя рекомендации и шаблонный текст всё равно будут выведены. Пустой список рекомендаций
не вызывает модель. В Docker переменные передаются только сервису `api` из корневого `.env`.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `OPENAI_API_KEY` | пусто | Без ключа сразу используются шаблоны |
| `OPENAI_MODEL` | `gpt-4o-mini` | Модель с поддержкой Responses и Structured Outputs |
| `OPENAI_TIMEOUT_SECONDS` | `7` | Общий deadline запроса, допустимо `0 < timeout <= 8` |
| `LLM_ENABLED` | `true` | `false` отключает сетевые запросы |

## Контракт для backend-разработчика

Сохранены порты `RecommendationEngine.rank(context)` и
`await ExplanationProvider.explain(context) -> Mapping[event_id, str]`.
Новые поля dataclass добавлены с defaults, старые обязательные аргументы сохранены.
`RecommendationContext.target` теперь допускает `None`, когда карьерной цели нет.
Статусы участия поддерживают значения датасета без преобразования в `missed`.

Готовая точка подключения:

```python
from app.application.recommendations import RecommendationService
from app.domain.ranking import DeterministicRecommendationEngine
from app.infrastructure.explanations import ExplanationSettings, OpenAIExplanationProvider

service = RecommendationService(
    DeterministicRecommendationEngine(),
    OpenAIExplanationProvider(ExplanationSettings()),
)

# context собирается из БД после проверки доступа.
results = await service.recommend(context, skill_names=skill_names)
for result in results:
    facts = result.facts       # RankedRecommendation, в исходном порядке engine
    text = result.explanation  # Только человекочитаемое объяснение
```

`context` содержит текущие навыки сотрудника, целевые требования, его историю,
каталог событий, язык и явную дату `as_of`. `target.grade` — **целевой** грейд;
`target.required_skills` — требования именно этого грейда. Для истории типов передавайте
полный каталог в `candidates`, engine сам фильтрует доступность. Вызов не меняет входные данные.

Backend преобразует результаты в свой HTTP DTO, добавляет названия событий и `priority`
по позиции в результате. Формулы и сортировка на frontend не дублируются.
Нет нового публичного незащищённого AI endpoint; существующие HTTP-маршруты не изменены.

Если scoring уже реализован отдельно, можно подключить только объяснения:

```python
from app.domain.models import ExplanationContext

context = ExplanationContext(locale="ru", recommendations=ranked, skill_names=skill_names)
texts = await provider.explain(context)
# Диагностика без глобального mutable-состояния:
details = await provider.explain_with_metadata(context)
# details.source = openai | template, details.fallback_reason = ...
```

Это альтернативные вызовы: не вызывайте оба для одного запроса, иначе будет два обращения к API.
Минимальные обязательные факты в `RankedRecommendation`: event_id, score, target_grade,
положительные skill_gaps, положительные expected_gains для этих gaps, reason_codes.
Дополнительно передавайте current_grade, current_levels, required_levels,
history_summary (числа участий **того же типа активности**) и readiness_before/after.
Текущие/требуемые уровни и значения readiness передаются парами.
Неполные минимальные контракты не приводят к выдумыванию истории или текущего уровня.
Некорректные факты вызывают `ValueError`; fallback не маскирует ошибки scoring.

Для connection pooling можно передать `client=httpx.AsyncClient()` в провайдер,
создать его в lifespan и закрыть там же. Без внешнего client провайдер создаёт и закрывает
клиент на каждый сетевой вызов. Отмена пользовательского запроса не подавляется.

## Правила расчёта v1

Это явная политика реализации, а не веса, заданные организаторами. Иллюстративная
формула из `team-tasks.md` не использована как утверждённое требование.

- Пропущенный навык = 0 согласно README датасета. Неизвестный skill ID отклоняется
  read-only адаптером; DB-импорт должен проверять ссылки тем же образом.
- `gap = max(required - current, 0)`. Критический навык имеет вес 2, остальные — 1.
- `readiness = 100 × sum(weight × min(current, required)) / sum(weight × required)`,
  округление до 2 знаков. Нет цели или все требования нулевые → `None`, рекомендации пусты.
  Readiness является индикатором покрытия требований, а не обещанием повышения.
- Для raw-датасета явная `career_goal` определяет цель, иначе берётся следующий грейд
  текущей роли по порядку Junior → Middle → Senior → Lead из dataset README.
  Lead без цели → `None`. Новая роль/цель должна иметь соответствующий role_profile.
- Исключаются mandatory/compliance/onboarding, несовпадение текущей роли/грейда,
  невыполненные prerequisites, завершённые неповторяемые и уже начатые активности.
  Scheduled-события требуют сессию не раньше `as_of`; self_paced доступны всегда.
  Work format не используется для запрета offline: такого правила в датасете нет.
- Реальный gain считается через `apply_skill_effects` с учётом max_level и ограничения 5.
  Кандидат должен уменьшать хотя бы один целевой gap. Выходные expected_gains включают
  весь положительный рост, skill_gaps — затрагиваемые дефициты целевого грейда.
- `impact = sum(weight × min(gap, actual_gain)) / sum(weight × gap)`.
  История учитывается только для того же типа события, без будущих записей.
  `fit = max(0.25, (completed + 1) / (completed + missed + no_show + dropped + declined + 2))`.
  Без истории fit = 0.5; причины незавершения не интерпретируются как отсутствие интереса.
- `score = round(0.85 × impact + 0.15 × fit, 6)`; сортировка по убыванию score,
  затем лексикографически по event_id. Возвращаются первые 0–3 события, без случайности.

`DatasetSnapshot` — **адаптер для автономной проверки**, не замена импорта backend.
Он читает дату среза `2026-10-01` из meta, нормализует отсутствующие навыки и применяет
завершения строго после last_review_date в порядке `(date, record_id)`.
Повторяемый клуб EV_036 обрабатывается согласно правилу датасета.
В реальном CSV ежегодные обязательные compliance-курсы повторяются, хотя общее описание
говорит о запрете повторов: адаптер допускает такие повторения, если они не имеют skill effects.

**Важно для интеграции:** в БД текущие навыки должны быть материализованы один раз.
После completion backend применяет эффект в транзакции и передаёт engine новые навыки.
Нельзя снова прогонять текущий профиль через восстановление raw-истории — это удвоит gain.
Повторное/конкурентное completion и запись результатов остаются ответственностью backend.

## Как работает LLM и защита фактов

Используется [OpenAI Responses со Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Python строит локализованные подтверждённые предложения о грейде, текущем уровне,
gap, gain, readiness и доступной истории. LLM возвращает JSON-план: event_id и список
`{fact_id, wording: "concise" | "supportive"}`. Она выбирает порядок и формулировку
из разрешённых вариантов; итоговый текст собирается локально.

Это **ограниченная генерация объяснения**, а не свободный текст модели. Числа, навыки
и история не берутся из произвольной строки LLM. Проверяется полный набор фактов
для каждого события, отсутствие дублей/чужих IDs и допустимость вариантов формулировок.
Поэтому неизвестные факты или попытка изменить score не попадают в пользовательский ответ.
Выбор и порядок самих рекомендаций всегда остаются у Python engine.

Отправляются только выбранные обезличенные факты: без employee_id, имени, руководителя,
полной истории или полного датасета. `store=false`, один пакетный запрос на 1–3 рекомендации,
без автоматических повторов. Сырые ответы, факты и ключ не логируются.

Нет ключа / отключён LLM / timeout / rate limit / API error / refusal / некорректный JSON
или план → шаблонные тексты из тех же фактов. `explain_with_metadata` сообщает источник
и код причины; эти поля можно добавить в серверную диагностику. Исключения engine
остаются видимыми, а успешный fallback сохраняет работоспособность приложения.

## Проверки и оставшаяся интеграция

```powershell
# Из корня:
.venv/Scripts/python.exe -m pytest -c apps/api/pytest.ini apps/api/tests -q
docker compose config --quiet
```

Покрыты критический gap против самого низкого навыка, история, prerequisites,
сессии, caps, пустые результаты, tie-break, все 200 профилей на RU/KK/EN,
профиль с новым ID, восстановление после аттестации и пересчёт после completion.
MockTransport проверяет формат запроса, успешный ответ, сохранение порядка,
таймаут, 401/429/500, потерю сети, отказ модели, чужие/дублированные IDs,
пропущенные/выдуманные факты, отсутствие ключа и disabled-режим.

Реальный сетевой smoke-test требует локального ключа и доступа к выбранной модели.
После подключения backend нужно проверить JWT → загрузка контекста → recommendations →
completion → новые навыки/readiness → новые recommendations. DB, JWT и HTTP DTO этот модуль
не реализует. UI интеграция и оценка качества на профилях жюри остаются отдельными проверками.
