import { NextRequest, NextResponse } from 'next/server';

const cookieName = 'cq_session';
const id = '[^/]+';
const getRoutes = [ /^health$/, /^ready$/, /^auth\/me$/, /^auth\/demo\/employees$/, /^employees$/, new RegExp(`^employees/${id}(?:/(?:skills|trajectory|activities))?$`), /^events$/, new RegExp(`^events/${id}$`), /^hr\/(?:dashboard|skill-gaps|employees|activity-stats|recommendation-coverage)$/ ];
const postRoutes = [ /^auth\/demo\/(?:employee|hr)$/, /^datasets\/import$/, /^recommendations$/, new RegExp(`^employees/${id}/recommendations$`), new RegExp(`^employees/${id}/activities/${id}/complete$`) ];
const headers = { 'Cache-Control': 'no-store' };
const maxImportBytes = 42 * 1024 * 1024;

async function importBody(request: NextRequest): Promise<ArrayBuffer | null> {
  if (Number(request.headers.get('content-length') || 0) > maxImportBytes) return null;
  const reader = request.body?.getReader();
  if (!reader) return new ArrayBuffer(0);
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maxImportBytes) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  return body.buffer;
}

function sameOrigin(request: NextRequest) {
  try {
    const origin = new URL(request.headers.get('origin') || '');
    // Next.js may normalize nextUrl.hostname to its internal bind address.
    // Host retains the public host/port requested by the browser.
    return ['http:', 'https:'].includes(origin.protocol) && origin.host === request.headers.get('host');
  } catch { return false; }
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.some(part => part === '.' || part === '..' || /[\\/\x00-\x1f]/.test(part))) return NextResponse.json({ detail: 'Not found' }, { status: 404, headers });
  const route = path.join('/');
  if (request.method === 'POST' && !sameOrigin(request)) {
    return NextResponse.json({ detail: 'Недопустимый источник запроса.' }, { status: 403, headers });
  }
  if (route === 'auth/logout' && request.method === 'POST') {
    const response = NextResponse.json({ ok: true }, { headers });
    response.cookies.delete(cookieName);
    return response;
  }
  const allowed = request.method === 'GET' ? getRoutes : postRoutes;
  if (!allowed.some(pattern => pattern.test(route))) return NextResponse.json({ detail: 'Not found' }, { status: 404, headers });
  const token = request.cookies.get(cookieName)?.value;
  const isLogin = route === 'auth/demo/employee' || route === 'auth/demo/hr';
  if (!['health', 'ready', 'auth/demo/employees'].includes(route) && !isLogin && !token) return NextResponse.json({ detail: 'Unauthorized' }, { status: 401, headers });
  try {
    const payload = request.method === 'POST' ? (route === 'datasets/import' ? await importBody(request) : await request.arrayBuffer()) : undefined;
    if (payload === null) return NextResponse.json({ detail: 'Размер запроса превышает 42 МБ.' }, { status: 413, headers });
    if (route === 'recommendations' && payload) {
      if (payload.byteLength > 4096) return NextResponse.json({ detail: 'Запрос слишком большой.' }, { status: 413, headers });
      try {
        const body = JSON.parse(new TextDecoder().decode(payload));
        if (!body || typeof body.employee_id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(body.employee_id)
            || !['ru', 'kk', 'en'].includes(body.locale)) throw new Error('Invalid request');
      } catch {
        return NextResponse.json({ detail: 'Проверьте сотрудника и язык.' }, { status: 400, headers });
      }
    }
    const upstreamHeaders = new Headers();
    const idempotencyKey = request.headers.get('idempotency-key');
    if (idempotencyKey && /\/complete$/.test(route)) upstreamHeaders.set('Idempotency-Key', idempotencyKey);
    if (token) upstreamHeaders.set('Authorization', `Bearer ${token}`);
    const contentType = request.headers.get('content-type');
    if (contentType) upstreamHeaders.set('Content-Type', contentType);
    const base = (process.env.API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    const upstream = await fetch(`${base}/api/v1/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`, {
      method: request.method, headers: upstreamHeaders,
      body: payload,
      cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(route === 'recommendations' ? 125000 : route === 'datasets/import' ? 55000 : 12000),
    });
    const body = await upstream.json();
    if (isLogin && upstream.ok) {
      if (typeof body.access_token !== 'string') throw new Error('Invalid token');
      const identity = await fetch(`${base}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${body.access_token}` }, cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(5000) });
      const user = await identity.json();
      if (!identity.ok || !['employee', 'hr'].includes(user?.role) || (user.role === 'employee' && typeof user.employee_id !== 'string')) throw new Error('Invalid session');
      const response = NextResponse.json({ user }, { headers });
      response.cookies.set(cookieName, body.access_token, { httpOnly: true, sameSite: 'lax', secure: request.headers.get('origin')?.startsWith('https://'), path: '/' });
      return response;
    }
    const response = NextResponse.json(route === 'auth/me' && upstream.ok ? { user: body } : body, { status: upstream.status, headers });
    if (upstream.status === 401) response.cookies.delete(cookieName);
    return response;
  } catch {
    return NextResponse.json({ detail: 'Сервис временно недоступен.' }, { status: 503, headers });
  }
}

export const GET = proxy;
export const POST = proxy;
