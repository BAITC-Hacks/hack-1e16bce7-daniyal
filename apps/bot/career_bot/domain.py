from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

LOCAL_TZ = timezone(timedelta(hours=5))


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    due_at: datetime
    completed: bool = False


@dataclass(frozen=True)
class Employee:
    id: str
    joined_at: datetime
    last_participation: datetime | None
    tasks: tuple[Task, ...]


@dataclass(frozen=True)
class Reminder:
    key: str
    text: str


def reminders(employee: Employee, now: datetime, inactive_days: int = 14) -> list[Reminder]:
    """Pure rules. Completed work never produces a deadline reminder."""
    result = []
    today = now.astimezone(LOCAL_TZ).date().isoformat()
    for task in employee.tasks:
        if task.completed:
            continue
        delta = task.due_at - now
        due = task.due_at.astimezone(LOCAL_TZ).strftime('%d.%m.%Y %H:%M')
        identity = f'{task.id}:{task.due_at.isoformat()}'
        if delta <= timedelta(0):
            result.append(Reminder(f'overdue:{identity}:{today}',
                f'Дедлайн прошёл: «{task.title}» ({due}, UTC+5). Заверши задание или обсуди перенос срока с куратором.'))
        elif delta <= timedelta(hours=24):
            result.append(Reminder(f'deadline:{identity}',
                f'До дедлайна меньше суток: «{task.title}». Срок — {due} (UTC+5). Проверь, всё ли готово.'))
    baseline = employee.last_participation or employee.joined_at
    days = (now - baseline).days
    if days >= inactive_days:
        # Weekly reminder anchored to last attendance, not to worker restart.
        week = (days - inactive_days) // 7
        result.append(Reminder(f'inactive:{baseline.isoformat()}:{week}',
            f'Ты уже {days} дней не участвовал в мероприятиях Career Quest. Выбери одно небольшое событие на эту неделю — возвращаться можно постепенно.'))
    return result


def within_sending_hours(now: datetime) -> bool:
    return 9 <= now.astimezone(LOCAL_TZ).hour < 20
