import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career_bot.adapters import Store, read_employees
from career_bot.domain import Employee, Task, reminders, within_sending_hours
from career_bot.service import SendError, deliver, handle_update

NOW = datetime(2026, 9, 23, 7, tzinfo=timezone.utc)  # Noon in UTC+5.


class FakeSender:
    def __init__(self):
        self.messages = []
        self.errors = {}

    def send(self, chat_id, text, app_url=None):
        if chat_id in self.errors:
            raise self.errors[chat_id]
        self.messages.append((chat_id, text, app_url))


class RulesTests(unittest.TestCase):
    def employee(self, days=14, tasks=()):
        return Employee('e1', NOW - timedelta(days=100), NOW - timedelta(days=days), tasks)

    def test_inactivity_boundary_and_weekly_key(self):
        self.assertEqual(reminders(self.employee(13), NOW), [])
        employee = self.employee(14)
        self.assertEqual(len(reminders(employee, NOW)), 1)
        self.assertEqual(reminders(employee, NOW)[0].key, reminders(employee, NOW + timedelta(days=6))[0].key)
        self.assertNotEqual(reminders(employee, NOW)[0].key, reminders(employee, NOW + timedelta(days=7))[0].key)

    def test_first_participation_and_future_dates(self):
        employee = replace(self.employee(), last_participation=None, joined_at=NOW - timedelta(days=15))
        self.assertIn('15 дней', reminders(employee, NOW)[0].text)
        self.assertEqual(reminders(replace(employee, joined_at=NOW + timedelta(days=1)), NOW), [])

    def test_deadlines_boundary_completed_and_rescheduled(self):
        tasks = (Task('soon', 'Soon', NOW + timedelta(hours=24)), Task('future', 'Future', NOW + timedelta(hours=25)), Task('done', 'Done', NOW - timedelta(days=1), True), Task('late', 'Late', NOW))
        result = reminders(self.employee(1, tasks), NOW)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0].key.startswith('deadline:'))
        self.assertTrue(result[1].key.startswith('overdue:'))
        moved = self.employee(1, (replace(tasks[0], due_at=NOW + timedelta(hours=23)),))
        self.assertNotEqual(result[0].key, reminders(moved, NOW)[0].key)

    def test_quiet_hours(self):
        self.assertFalse(within_sending_hours(NOW.replace(hour=3)))
        self.assertTrue(within_sending_hours(NOW.replace(hour=4)))
        self.assertTrue(within_sending_hours(NOW.replace(hour=14)))
        self.assertFalse(within_sending_hours(NOW.replace(hour=15)))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'bot.sqlite3'
        self.store = Store(self.path)
        self.sender = FakeSender()
        self.employee = Employee('e1', NOW - timedelta(days=100), NOW - timedelta(days=21), (Task('a', 'Задание', NOW + timedelta(hours=2)),))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def link(self, employee_id='e1', chat_id=123):
        token = self.store.invite(employee_id, NOW)
        self.assertTrue(self.store.bind(token, chat_id, NOW, {employee_id}))

    def command(self, text, chat_type='private', chat_id=123):
        update = {'message': {'chat': {'id': chat_id, 'type': chat_type}, 'from': {'id': chat_id}, 'text': text}}
        handle_update(update, [self.employee], self.store, self.sender, NOW)

    def test_one_use_expiry_reissue_and_conflicts(self):
        old = self.store.invite('e1', NOW)
        token = self.store.invite('e1', NOW)
        self.assertFalse(self.store.bind(old, 123, NOW, {'e1'}))
        self.assertTrue(self.store.bind(token, 123, NOW, {'e1'}))
        self.assertFalse(self.store.bind(token, 999, NOW, {'e1'}))
        other = self.store.invite('e1', NOW)
        self.assertFalse(self.store.bind(other, 999, NOW, {'e1'}))
        expired = self.store.invite('e2', NOW)
        self.assertFalse(self.store.bind(expired, 234, NOW + timedelta(minutes=15), {'e2'}))
        self.assertFalse(self.store.bind('e1', 234, NOW, {'e1'}))

    def test_private_chat_only_and_removed_employee(self):
        token = self.store.invite('e1', NOW)
        self.command(f'/start {token}', 'group')
        self.assertEqual(self.sender.messages, [])
        self.assertIsNone(self.store.subscriber(123))
        self.assertFalse(self.store.bind(token, 123, NOW, set()))

    def test_commands_pause_resume_stop(self):
        self.link()
        self.command('/pause')
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW), 0)
        self.command('/resume')
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW), 1)
        self.command('/status')
        self.assertIn('включены', self.sender.messages[-1][1])
        self.command('/stop')
        self.assertIsNone(self.store.subscriber(123))

    def test_deduplication_survives_restart_and_hour_cap(self):
        self.link()
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW), 1)
        self.assertEqual(len(self.sender.messages), 1)
        self.assertIn('меньше суток', self.sender.messages[0][1])
        self.assertIn('21 дней', self.sender.messages[0][1])
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW + timedelta(hours=1)), 0)
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW + timedelta(hours=3)), 1)
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW + timedelta(hours=4)), 0)
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW + timedelta(days=1)), 1)

    def test_failed_delivery_not_marked_and_other_user_receives(self):
        self.link()
        self.link('e2', 234)
        self.sender.errors[123] = SendError(500)
        second = replace(self.employee, id='e2')
        self.assertEqual(deliver([self.employee, second], self.store, self.sender, NOW), 1)
        self.assertFalse(self.store.sent('e1', reminders(self.employee, NOW)[0].key))
        self.sender.errors.clear()
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW + timedelta(minutes=2)), 1)

    def test_rate_limit_and_block(self):
        self.link()
        self.sender.errors[123] = SendError(429, 120)
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW), 0)
        self.assertEqual(float(self.store.state('retry_all')), (NOW + timedelta(seconds=120)).timestamp())
        self.sender.errors[123] = SendError(403)
        deliver([self.employee], self.store, self.sender, NOW + timedelta(minutes=3))
        self.assertEqual(self.store.subscriber(123)['paused'], 1)

    def test_no_reminders_for_unlinked_or_completed(self):
        self.assertEqual(deliver([self.employee], self.store, self.sender, NOW), 0)
        self.link()
        completed = replace(self.employee, last_participation=NOW, tasks=(replace(self.employee.tasks[0], completed=True),))
        self.assertEqual(deliver([completed], self.store, self.sender, NOW), 0)

    def test_snapshot_validation(self):
        path = Path(self.temp.name) / 'input.json'
        item = {'id': 'e1', 'joined_at': '2026-01-01T00:00:00+00:00', 'tasks': []}
        path.write_text(json.dumps({'version': 1, 'employees': [item]}))
        self.assertEqual(read_employees(path)[0].id, 'e1')
        path.write_text(json.dumps({'version': 1, 'employees': [item, item]}))
        with self.assertRaises(ValueError): read_employees(path)
        item['joined_at'] = '2026-01-01T00:00:00'
        path.write_text(json.dumps({'version': 1, 'employees': [item]}))
        with self.assertRaises(ValueError): read_employees(path)


if __name__ == '__main__':
    unittest.main()
