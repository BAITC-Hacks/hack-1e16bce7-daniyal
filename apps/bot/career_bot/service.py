from datetime import datetime
from typing import Protocol

from .domain import Employee, reminders, within_sending_hours


class SendError(Exception):
    def __init__(self, code: int = 0, retry_after: int = 30):
        self.code = code
        self.retry_after = max(1, retry_after)
        super().__init__(f'Telegram request failed (code={code})')


class Sender(Protocol):
    def send(self, chat_id: int, text: str, app_url: str | None = None): ...


class Repository(Protocol):
    def bind(self, token: str, chat_id: int, now: datetime, allowed_ids: set[str]) -> bool: ...
    def subscriber(self, chat_id: int): ...
    def subscribers(self): ...
    def pause(self, chat_id: int, paused: bool): ...
    def stop(self, chat_id: int): ...
    def sent(self, employee_id: str, key: str) -> bool: ...
    def mark_sent(self, employee_id: str, keys: list[str], now: datetime): ...
    def state(self, key: str, default: str = '0') -> str: ...
    def set_state(self, key: str, value: str): ...


HELP = ('Career Quest — напоминания о развитии.\n'
        '/status — статус подписки\n/pause — пауза\n/resume — возобновить\n'
        '/stop — отключить и отвязать Telegram\n/help — помощь\n'
        'Для подключения нужна одноразовая ссылка от администратора. '
        'Напоминания приходят с 09:00 до 20:00 (UTC+5).')


def handle_update(update: dict, employees: list[Employee], store: Repository, sender: Sender, now: datetime):
    message = update.get('message', {})
    chat = message.get('chat', {})
    chat_id = chat.get('id')
    if chat.get('type') != 'private' or type(chat_id) is not int or message.get('from', {}).get('id') != chat_id:
        return
    text = message.get('text', '')
    if not isinstance(text, str):
        return
    parts = text.split(maxsplit=1)
    command = parts[0].split('@')[0] if parts else ''
    if command == '/start' and len(parts) == 2:
        bound = store.bind(parts[1].strip(), chat_id, now, {e.id for e in employees})
        reply = ('Уведомления подключены. ' + HELP) if bound else 'Ссылка недействительна, истекла или профиль уже привязан. Запроси новую ссылку у администратора.'
    elif command == '/stop':
        store.stop(chat_id)
        reply = 'Telegram отвязан. Напоминаний больше не будет. Для подключения нужна новая ссылка.'
    elif command in ('/pause', '/resume', '/status'):
        row = store.subscriber(chat_id)
        if not row:
            reply = 'Telegram ещё не подключён. Запроси одноразовую ссылку у администратора.'
        elif command == '/status':
            reply = 'Уведомления на паузе.' if row['paused'] else 'Уведомления включены. Время отправки: 09:00–20:00 (UTC+5).'
        else:
            store.pause(chat_id, command == '/pause')
            reply = 'Уведомления на паузе. /resume — возобновить.' if command == '/pause' else 'Уведомления снова включены.'
    else:
        reply = HELP
    sender.send(chat_id, reply)


def deliver(employees: list[Employee], store: Repository, sender: Sender, now: datetime,
            app_url: str | None = None, inactive_days: int = 14) -> int:
    if not within_sending_hours(now):
        return 0
    if now.timestamp() < float(store.state('retry_all')):
        return 0
    sent = 0
    by_id = {e.id: e for e in employees}
    for subscriber in store.subscribers():
        employee_id = subscriber['employee_id']
        employee = by_id.get(employee_id)
        if not employee:
            continue
        if now.timestamp() < float(store.state(f'retry:{employee_id}')):
            continue
        # One digest per employee per hour, including after worker restarts.
        if now.timestamp() - float(store.state(f'last_digest:{employee_id}')) < 3600:
            continue
        pending = [r for r in reminders(employee, now, inactive_days) if not store.sent(employee_id, r.key)][:5]
        if not pending:
            continue
        text = 'Career Quest\n\n' + '\n\n'.join(r.text for r in pending) + '\n\n/pause — приостановить уведомления'
        try:
            sender.send(subscriber['chat_id'], text, app_url)
        except SendError as exc:
            if exc.code == 403:
                store.pause(subscriber['chat_id'], True)
            elif exc.code == 401:
                raise
            elif exc.code == 429:
                store.set_state('retry_all', str(now.timestamp() + exc.retry_after))
                break
            else:
                store.set_state(f'retry:{employee_id}', str(now.timestamp() + max(60, exc.retry_after)))
            continue
        # Failed sends are not marked. Telegram has no idempotency key for sendMessage.
        store.mark_sent(employee_id, [r.key for r in pending], now)
        store.set_state(f'last_digest:{employee_id}', str(now.timestamp()))
        sent += 1
    return sent
