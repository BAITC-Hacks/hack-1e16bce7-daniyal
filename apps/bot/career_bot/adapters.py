import hashlib
import json
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .domain import Employee, Task
from .service import SendError


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Dates must include UTC offset')
    return parsed.astimezone(timezone.utc)


def read_employees(path: Path) -> list[Employee]:
    source = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(source, dict) or source.get('version') != 1 or not isinstance(source.get('employees'), list):
        raise ValueError('Expected version=1 and employees array')
    employees = []
    ids = set()
    for item in source['employees']:
        employee_id = item['id']
        if not isinstance(employee_id, str) or not employee_id or employee_id in ids:
            raise ValueError('Employee IDs must be nonempty and unique')
        ids.add(employee_id)
        tasks, task_ids = [], set()
        for t in item.get('tasks', []):
            if not isinstance(t['id'], str) or not t['id'] or t['id'] in task_ids:
                raise ValueError('Task IDs must be nonempty and unique per employee')
            task_ids.add(t['id'])
            if not isinstance(t['title'], str) or not 1 <= len(t['title']) <= 200 or type(t.get('completed', False)) is not bool:
                raise ValueError('Invalid task title or completion flag')
            tasks.append(Task(t['id'], t['title'], timestamp(t['due_at']), t.get('completed', False)))
        joined = timestamp(item['joined_at'])
        attended = timestamp(item['last_participation']) if item.get('last_participation') else None
        if attended and attended < joined:
            raise ValueError('Participation cannot precede joining')
        employees.append(Employee(employee_id, joined, attended, tuple(tasks)))
    return employees


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS subscribers (
              employee_id TEXT PRIMARY KEY, chat_id INTEGER UNIQUE NOT NULL, paused INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS invites (
              digest TEXT PRIMARY KEY, employee_id TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS deliveries (
              employee_id TEXT NOT NULL, reminder_key TEXT NOT NULL, sent_at REAL NOT NULL,
              PRIMARY KEY(employee_id, reminder_key));
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def invite(self, employee_id: str, now: datetime) -> str:
        token = secrets.token_urlsafe(24)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.db:
            self.db.execute('DELETE FROM invites WHERE employee_id=? OR expires<=?', (employee_id, now.timestamp()))
            self.db.execute('INSERT INTO invites VALUES (?,?,?)', (digest, employee_id, (now + timedelta(minutes=15)).timestamp()))
        return token

    def bind(self, token: str, chat_id: int, now: datetime, allowed_ids: set[str]) -> bool:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT employee_id FROM invites WHERE digest=? AND expires>?', (digest, now.timestamp())).fetchone()
            if not row or row['employee_id'] not in allowed_ids:
                return False
            # Never overwrite an existing pairing using a different invitation.
            conflict = self.db.execute('SELECT 1 FROM subscribers WHERE (employee_id=? AND chat_id!=?) OR (chat_id=? AND employee_id!=?)', (row['employee_id'], chat_id, chat_id, row['employee_id'])).fetchone()
            if conflict:
                return False
            self.db.execute('INSERT INTO subscribers VALUES (?,?,0) ON CONFLICT(employee_id) DO UPDATE SET paused=0', (row['employee_id'], chat_id))
            self.db.execute('DELETE FROM invites WHERE digest=?', (digest,))
        return True

    def subscriber(self, chat_id: int):
        return self.db.execute('SELECT * FROM subscribers WHERE chat_id=?', (chat_id,)).fetchone()

    def subscribers(self):
        return self.db.execute('SELECT * FROM subscribers WHERE paused=0').fetchall()

    def pause(self, chat_id: int, paused: bool):
        with self.db:
            self.db.execute('UPDATE subscribers SET paused=? WHERE chat_id=?', (int(paused), chat_id))

    def stop(self, chat_id: int):
        with self.db:
            self.db.execute('DELETE FROM subscribers WHERE chat_id=?', (chat_id,))

    def sent(self, employee_id: str, key: str) -> bool:
        return self.db.execute('SELECT 1 FROM deliveries WHERE employee_id=? AND reminder_key=?', (employee_id, key)).fetchone() is not None

    def mark_sent(self, employee_id: str, keys: list[str], now: datetime):
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO deliveries VALUES (?,?,?)', [(employee_id, key, now.timestamp()) for key in keys])

    def state(self, key: str, default: str = '0') -> str:
        row = self.db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
        return row['value'] if row else default

    def set_state(self, key: str, value: str):
        with self.db:
            self.db.execute('INSERT INTO state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))


class TelegramError(SendError):
    pass


class Telegram:
    def __init__(self, token: str):
        self._token = token

    def call(self, method: str, payload: dict):
        request = urllib.request.Request(f'https://api.telegram.org/bot{self._token}/{method}',
            data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read())
                wait = int(body.get('parameters', {}).get('retry_after', 30))
            except (ValueError, TypeError):
                wait = 30
            raise TelegramError(exc.code, wait) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            # Never log the request URL, token or raw Telegram response.
            raise TelegramError() from None
        if not result.get('ok'):
            raise TelegramError(result.get('error_code', 0), result.get('parameters', {}).get('retry_after', 30))
        return result['result']

    def send(self, chat_id: int, text: str, app_url: str | None = None):
        payload = {'chat_id': chat_id, 'text': text}
        if app_url:
            payload['reply_markup'] = {'inline_keyboard': [[{'text': 'Открыть Career Quest', 'url': app_url}]]}
        return self.call('sendMessage', payload)

    def updates(self, offset: int):
        return self.call('getUpdates', {'offset': offset, 'timeout': 25, 'allowed_updates': ['message']})
