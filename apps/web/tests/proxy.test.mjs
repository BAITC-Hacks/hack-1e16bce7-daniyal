import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fixtureApi } from './fixture-api.mjs';

const origin = 'http://127.0.0.1:18002';
let upstream;
let web;
let logs = '';
const request = (path, options = {}) => fetch(`${origin}/api/v1/${path}`, options);
const post = (value, cookie) => ({ method: 'POST', headers: { origin, 'Content-Type': 'application/json', ...(cookie ? { cookie } : {}) }, body: JSON.stringify(value) });
async function login(role = 'employee') {
  const response = await request(`auth/demo/${role}`, post(role === 'hr' ? { password: 'fixture-hr' } : { employee_id: 'JURY-42' }));
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.access_token, undefined);
  const cookie = response.headers.get('set-cookie');
  assert.match(cookie, /HttpOnly/i);
  assert.match(cookie, /SameSite=lax/i);
  return cookie.split(';')[0];
}

before(async () => {
  upstream = fixtureApi();
  upstream.listen(18001, '127.0.0.1');
  await once(upstream, 'listening');
  web = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '-p', '18002', '-H', '127.0.0.1'], { env: { ...process.env, API_URL: 'http://127.0.0.1:18001' }, stdio: ['ignore', 'pipe', 'pipe'] });
  web.stdout.on('data', chunk => { logs += chunk; });
  web.stderr.on('data', chunk => { logs += chunk; });
  for (let attempt = 0; attempt < 100; attempt++) {
    try { if ((await request('health')).ok) return; } catch {}
    if (web.exitCode !== null) throw new Error(logs);
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Server did not start: ${logs}`);
});
after(async () => {
  if (web && web.exitCode === null) { web.kill(); await once(web, 'exit'); }
  if (upstream) { upstream.closeAllConnections(); await new Promise(resolve => upstream.close(resolve)); }
});

test('proxy restricts routes and refuses business requests without a session', async () => {
  assert.equal((await request('health')).status, 200);
  assert.equal((await request('employees/JURY-42')).status, 401);
  assert.equal((await request('admin/secrets')).status, 404);
  assert.equal((await request('employees/JURY-42/unknown')).status, 404);
  assert.equal((await request('auth/demo/employee', { ...post({}), headers: { origin: 'https://other.example', 'Content-Type': 'application/json' } })).status, 403);
});

test('session cookie forwards server authorization; completion refresh returns server values', async () => {
  const cookie = await login();
  assert.equal((await (await request('auth/me', { headers: { cookie } })).json()).user.employee_id, 'JURY-42');
  assert.equal((await request('hr/dashboard', { headers: { cookie } })).status, 403);
  assert.equal((await request('employees/another-id', { headers: { cookie } })).status, 403);
  assert.equal((await request('employees/JURY-42/activities/EV_014/complete', post({}, cookie))).status, 422);
  const completionRequest = post({}, cookie);
  completionRequest.headers['Idempotency-Key'] = 'proxy-test-completion';
  const complete = await request('employees/JURY-42/activities/EV_014/complete', completionRequest);
  assert.equal(complete.status, 200);
  assert.equal((await complete.json()).changes[0].after, 3);
  const again = await (await request('employees/JURY-42/activities/EV_014/complete', completionRequest)).json();
  assert.equal(again.already_completed, true);
  assert.deepEqual(again.changes, []);
  const recommendations = await request('employees/JURY-42/recommendations', post({ language: 'ru' }, cookie));
  assert.deepEqual(await recommendations.json(), []);
  const logout = await request('auth/logout', post({}, cookie));
  assert.match(logout.headers.get('set-cookie'), /expires=Thu, 01 Jan 1970/i);
});

test('HR analytics and multipart import preserve responses and validation errors', async () => {
  const cookie = await login('hr');
  assert.equal((await request('hr/dashboard', { headers: { cookie } })).status, 200);
  const missing = await request('datasets/import', { method: 'POST', headers: { origin, cookie }, body: new FormData() });
  assert.equal(missing.status, 422);
  assert.equal((await missing.json()).detail[0].loc[1], 'employees.json');
  const form = new FormData();
  form.set('mode', 'append');
  form.set('employees.json', new Blob(['{}'], { type: 'application/json' }), 'employees.json');
  form.set('activity_history.csv', new Blob(['record_id\n'], { type: 'text/csv' }), 'activity_history.csv');
  const imported = await request('datasets/import', { method: 'POST', headers: { origin, cookie }, body: form });
  assert.equal(imported.status, 200);
  assert.equal((await imported.json()).history_records, 2743);
});

test('unreachable upstream produces an explicit 503 without connection details', async () => {
  upstream.closeAllConnections();
  await new Promise(resolve => upstream.close(resolve));
  upstream = null;
  const response = await request('health');
  assert.equal(response.status, 503);
  assert.equal((await response.json()).detail, 'Сервис временно недоступен.');
});
