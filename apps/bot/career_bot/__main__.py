import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .adapters import Store, Telegram, TelegramError, read_employees
from .domain import reminders, within_sending_hours
from .service import deliver, handle_update


def load_env(path: Path):
    if not path.exists():
        return
    # Deliberately limited KEY=value format; no shell expansion or execution.
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key.strip()):
            raise ValueError('Invalid .env line: use KEY=value')
        os.environ.setdefault(key.strip(), value.strip().strip('\"\''))


def demo(path: Path, now: datetime):
    payload = {'version': 1, 'employees': [
        {'id': 'arman', 'joined_at': (now - timedelta(days=120)).isoformat(),
         'last_participation': (now - timedelta(days=21)).isoformat(), 'tasks': [
             {'id': 'architecture', 'title': 'Защита архитектуры', 'due_at': (now + timedelta(hours=20)).isoformat(), 'completed': False}]},
        {'id': 'daniyar', 'joined_at': (now - timedelta(days=60)).isoformat(),
         'last_participation': (now - timedelta(days=3)).isoformat(), 'tasks': [
             {'id': 'api', 'title': 'API Design Workshop', 'due_at': (now - timedelta(hours=2)).isoformat(), 'completed': False}]},
    ]}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Do not silently erase an operator's edited snapshot.
    with path.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description='Career Quest Telegram notifications')
    parser.add_argument('command', choices=['init-demo', 'preview', 'invite', 'run'])
    parser.add_argument('--data', type=Path, default=Path('data/employees.json'))
    parser.add_argument('--db', type=Path, default=Path('data/bot.sqlite3'))
    parser.add_argument('--employee', help='Employee id for invite')
    args = parser.parse_args()
    load_env(Path('.env'))
    now = datetime.now(timezone.utc)
    if args.command == 'init-demo':
        demo(args.data, now)
        print(f'Created mock snapshot: {args.data}')
        return 0
    employees = read_employees(args.data)
    inactive_days = int(os.getenv('INACTIVE_DAYS', '14'))
    if not 1 <= inactive_days <= 365:
        raise ValueError('INACTIVE_DAYS must be between 1 and 365')
    if args.command == 'preview':
        print('DRY RUN — no Telegram requests, no delivery state changes.')
        print('Sending window:', 'open' if within_sending_hours(now) else 'closed (09:00–20:00 UTC+5)')
        for employee in employees:
            for reminder in reminders(employee, now, inactive_days):
                print(f'[{employee.id}] {reminder.text}')
        return 0
    store = Store(args.db)
    try:
        if args.command == 'invite':
            if args.employee not in {e.id for e in employees}:
                raise ValueError('Choose an employee ID present in the snapshot')
            username = os.getenv('TELEGRAM_BOT_USERNAME', '').lstrip('@')
            if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', username):
                raise ValueError('Set TELEGRAM_BOT_USERNAME before generating a link')
            token = store.invite(args.employee, now)
            print('Private one-use link; valid for 15 minutes. Share only with this employee:')
            print(f'https://t.me/{username}?start={token}')
            return 0
        token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token):
            raise ValueError('Set TELEGRAM_BOT_TOKEN in apps/bot/.env (never in frontend)')
        app_url = os.getenv('CAREER_QUEST_URL', '').strip() or None
        if app_url and (urlparse(app_url).scheme != 'https' or not urlparse(app_url).hostname):
            raise ValueError('CAREER_QUEST_URL must be a public HTTPS URL or empty')
        sender = Telegram(token)
        # Inspect only: never delete an existing webhook behind the operator's back.
        if sender.call('getWebhookInfo', {}).get('url'):
            raise ValueError('This bot already has a webhook. Use a separate bot for this polling worker.')
        print('Worker running. Mock JSON snapshot; one worker per bot/database. Ctrl+C to stop.')
        while True:
            try:
                # Reload before every cycle so completed tasks stop producing reminders.
                employees = read_employees(args.data)
                updates = sender.updates(int(store.state('offset')))
                for update in updates:
                    try:
                        handle_update(update, employees, store, sender, datetime.now(timezone.utc))
                    except TelegramError as exc:
                        if exc.code != 403:
                            raise
                    store.set_state('offset', str(update['update_id'] + 1))
                count = deliver(employees, store, sender, datetime.now(timezone.utc), app_url, inactive_days)
                if count:
                    print(f'Digests delivered: {count}', flush=True)
            except TelegramError as exc:
                print(str(exc), file=sys.stderr, flush=True)
                if exc.code in (401, 409):
                    return 1
                time.sleep(min(max(exc.retry_after, 5), 3600))
            except (ValueError, KeyError, TypeError, OSError):
                print('Snapshot unavailable or invalid. No reminders sent; retry in 30 seconds.', file=sys.stderr, flush=True)
                time.sleep(30)
    finally:
        store.close()


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('Worker stopped.')
    except (ValueError, KeyError, TypeError, OSError, TelegramError) as exc:
        # Only explicit validation messages are shown; network URLs are never logged.
        print(f'Cannot start: {exc if isinstance(exc, (ValueError, TelegramError)) else type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)
