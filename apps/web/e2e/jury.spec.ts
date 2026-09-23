import { test, expect, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

const root = resolve(process.cwd(), '../..');
const envPath = resolve(root, process.env.JURY_ENV_FILE || '.env.jury');
const env = Object.fromEntries(readFileSync(envPath, 'utf8').split(/\r?\n/).filter(line => /^[A-Z_]+=/.test(line)).map(line => {
  const at = line.indexOf('='); return [line.slice(0, at), line.slice(at + 1).replace(/^["']|["']$/g, '')];
}));

async function loginHR(page: Page) {
  await page.goto('/hr');
  await page.getByLabel('Пароль HR', { exact: true }).fill(env.DEMO_HR_PASSWORD);
  await page.getByRole('button', { name: 'Войти →', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Рост команды начинается здесь.' })).toBeVisible();
}

test('jury import → recommendation → completion → persisted progress → HR', async ({ browser }, testInfo) => {
  const employeeId = `JURY-${Date.now()}`;
  const fixture = mkdtempSync(join(tmpdir(), 'cq-jury-'));
  const historyCount = Number(execFileSync(process.env.PYTHON || 'python', [join(root, 'scripts/create_jury_fixture.py'), fixture, '--id', employeeId], { encoding: 'utf8' }).trim());
  expect(historyCount).toBeGreaterThan(0);
  const origin = process.env.JURY_BASE_URL || 'http://127.0.0.1:3300';
  const adminContext = await browser.newContext({ baseURL: origin, viewport: { width: 1440, height: 1000 } });
  const employeeContext = await browser.newContext({ baseURL: origin, viewport: { width: 1440, height: 1000 } });
  const admin = await adminContext.newPage();
  const employee = await employeeContext.newPage();
  // Explicit URLs for independent role contexts; no API writes bypass the UI.
  const pageErrors: string[] = [];
  for (const page of [admin, employee]) {
    page.on('pageerror', error => pageErrors.push(error.message));
  }
  try {
    await loginHR(admin);
    const beforeHR = await (await admin.request.get(`${origin}/api/v1/hr/dashboard`)).json();
    await admin.goto('/hr/import');
    await admin.getByLabel('Добавить проверочные профили').check();
    await admin.getByLabel('employees.json', { exact: false }).setInputFiles(join(fixture, 'employees.json'));
    await admin.getByLabel('activity_history.csv', { exact: false }).setInputFiles(join(fixture, 'activity_history.csv'));
    await admin.getByRole('button', { name: 'Import Dataset →' }).click();
    await expect(admin.getByRole('heading', { name: 'Датасет загружен' })).toBeVisible();
    await expect(admin.getByRole('status')).toContainText(`Записей истории: ${historyCount}`);

    await employee.goto('/');
    await employee.getByPlaceholder('Выберите сотрудника или введите ID').fill(employeeId);
    await employee.getByRole('button', { name: 'Войти →', exact: true }).click();
    await expect(employee.getByRole('heading', { name: 'Jury Browser Test' })).toBeVisible();
    const api = `${origin}/api/v1/employees/${employeeId}`;
    const before = await (await employee.request.get(`${api}/trajectory`)).json();
    await expect(employee.locator('.cq-readiness')).toContainText(`${before.career_readiness}%`);
    await employee.goto('/recommendations');
    const cards = employee.locator('.cq-recommendation');
    await expect(cards.first()).toBeVisible();
    expect(await cards.count()).toBeLessThanOrEqual(3);
    const title = await cards.first().locator('h3').innerText();
    await expect(cards.first().locator('.cq-why')).toContainText('Почему рекомендуем');
    await cards.first().getByRole('button', { name: /Подробнее/ }).click();
    const dialog = employee.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: title, exact: true })).toBeVisible();
    const completedResponse = employee.waitForResponse(response => response.url().endsWith('/complete') && response.request().method() === 'POST');
    await dialog.getByRole('button', { name: 'Завершить в демо' }).click();
    const completed = await completedResponse;
    expect(completed.status()).toBe(200);
    const result = await completed.json();
    expect(result.changes.length).toBeGreaterThan(0);
    expect(result.career_readiness_after).toBeGreaterThan(before.career_readiness);
    await expect(employee.getByRole('heading', { name: 'Активность завершена!' })).toBeVisible();
    for (const change of result.changes) {
      await expect(employee.locator('.cq-completion-changes')).toContainText(`${change.before} → ${change.after}`);
    }
    await expect(cards.filter({ has: employee.getByRole('heading', { name: title, exact: true }) })).toHaveCount(0);
    await employee.goto('/career');
    await expect(employee.locator('.cq-readiness')).toContainText(`${result.career_readiness_after}%`);
    for (const change of result.changes) {
      await expect(employee.getByRole('progressbar', { name: new RegExp(`${change.name}: текущий уровень ${change.after},`) }).first()).toBeVisible();
    }
    await employee.reload();
    await expect(employee.locator('.cq-readiness')).toContainText(`${result.career_readiness_after}%`);
    await employee.screenshot({ path: testInfo.outputPath('employee-progress.png'), fullPage: true });
    await employee.goto('/history');
    await expect(employee.getByRole('row').filter({ hasText: title })).toContainText('Завершено');
    expect((await employee.request.get(`${origin}/api/v1/hr/dashboard`)).status()).toBe(403);

    await admin.goto('/hr/employees');
    await admin.getByPlaceholder('Имя, ID или роль').fill(employeeId);
    await expect(admin.getByRole('row').filter({ hasText: employeeId })).toContainText(`${result.career_readiness_after}%`);
    await admin.getByRole('button', { name: `Открыть профиль ${employeeId}`, exact: true }).click();
    await expect(admin.locator('.cq-readiness')).toContainText(`${result.career_readiness_after}%`);
    await admin.getByRole('button', { name: 'История', exact: true }).click();
    await expect(admin.getByRole('row').filter({ hasText: title })).toContainText('Завершено');
    await admin.goto('/hr');
    const afterHR = await (await admin.request.get(`${origin}/api/v1/hr/dashboard`)).json();
    expect(afterHR.employee_count).toBe(beforeHR.employee_count + 1);
    expect(afterHR.completed_activities).toBeGreaterThan(beforeHR.completed_activities);
    await expect(admin.getByRole('heading', { name: 'Top Skill Gaps' })).toBeVisible();
    await admin.screenshot({ path: testInfo.outputPath('hr-overview.png'), fullPage: true });
    await employee.setViewportSize({ width: 390, height: 844 });
    await employee.goto('/career');
    await expect(employee.locator('.cq-readiness')).toContainText(`${result.career_readiness_after}%`);
    expect(await employee.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await employee.screenshot({ path: testInfo.outputPath('employee-mobile.png'), fullPage: true });
    expect(pageErrors).toEqual([]);
    const report = testInfo.outputPath('verified-result.json');
    writeFileSync(report, JSON.stringify({ employeeId, historyCount, event: title, before: before.career_readiness, after: result.career_readiness_after, changes: result.changes }, null, 2));
    await testInfo.attach('verified-result', { path: report, contentType: 'application/json' });
  } finally {
    await adminContext.close();
    await employeeContext.close();
    rmSync(fixture, { recursive: true, force: true });
  }
});
