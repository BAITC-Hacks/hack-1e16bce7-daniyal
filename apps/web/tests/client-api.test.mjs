import { test, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

// Execute the real TS client adapter without adding a test runtime dependency.
const source = await readFile(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { api, jsonPost } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`);
afterEach(() => mock.restoreAll());

function respond(body, status = 200) {
  return mock.method(globalThis, 'fetch', async () => Response.json(body, { status }));
}

test('existing FastAPI profile and skill wrappers become display values without scoring', async () => {
  const transport = respond({ employee_id: 'JURY-42', grade: 'Middle' });
  assert.equal((await api('employees/JURY-42')).career_readiness, null);
  transport.mock.mockImplementation(async () => Response.json({ employee_id: 'JURY-42', items: [{ skill_id: 'S1', name: 'Design', level: 3, assessed_level: 2 }] }));
  assert.deepEqual(await api('employees/JURY-42/skills'), [{ skill_id: 'S1', name: 'Design', current_level: 3, required_level: null }]);
});

test('history retains backend pagination and all dataset statuses', async () => {
  respond({ items: [{ record_id: 'R1', event_title: 'Workshop', status: 'no_show' }], total: 123, limit: 50, offset: 50 });
  const page = await api('employees/JURY-42/activities?limit=50&offset=50');
  assert.equal(page.items[0].title, 'Workshop');
  assert.equal(page.items[0].status, 'no_show');
  assert.equal(page.total, 123);
  assert.equal(page.offset, 50);
});

test('completion errors reject and FastAPI validation includes field location', async () => {
  respond({ detail: [{ loc: ['body', 'employees.json', 12], msg: 'Unknown skill' }] }, 422);
  await assert.rejects(api('datasets/import', jsonPost({})), /body → employees.json → 12: Unknown skill/);
});

test('invalid HR credentials show a login error, not a successful session', async () => {
  respond({ detail: 'Invalid credentials' }, 401);
  await assert.rejects(api('auth/demo/hr', jsonPost({ password: 'wrong' })), /Проверьте данные для входа/);
});
