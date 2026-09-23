import { NextResponse } from 'next/server';

// Only explicitly supported backend routes are reachable through this proxy.
export async function GET(_request: Request, context: { params: Promise<{ endpoint: string }> }) {
  const { endpoint } = await context.params;
  if (!['health', 'ready', 'employees'].includes(endpoint)) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }
  try {
    const base = (process.env.API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    const response = await fetch(`${base}/api/v1/${endpoint}`, {
      cache: 'no-store', signal: AbortSignal.timeout(5000),
    });
    return NextResponse.json(await response.json(), {
      status: response.status, headers: { 'Cache-Control': 'no-store' },
    });
  } catch {
    return NextResponse.json({ status: 'unavailable' }, {
      status: 503, headers: { 'Cache-Control': 'no-store' },
    });
  }
}

export async function POST(request: Request, context: { params: Promise<{ endpoint: string }> }) {
  const { endpoint } = await context.params;
  if (endpoint !== 'recommendations') {
    return NextResponse.json({ detail: 'Not found' }, { status: 404 });
  }
  let body;
  try {
    const raw = await request.text();
    if (raw.length > 4096) return NextResponse.json({ detail: 'Запрос слишком большой.' }, { status: 413 });
    body = JSON.parse(raw);
    if (!body || typeof body.employee_id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(body.employee_id)
        || !['ru', 'kk', 'en'].includes(body.locale)) throw new Error('Invalid request');
  } catch {
    return NextResponse.json({ detail: 'Проверьте сотрудника и язык.' }, { status: 400 });
  }
  try {
    const base = (process.env.API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    const response = await fetch(`${base}/api/v1/recommendations`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ employee_id: body.employee_id, locale: body.locale }),
      cache: 'no-store', signal: AbortSignal.timeout(9500),
    });
    return NextResponse.json(await response.json(), {
      status: response.status, headers: { 'Cache-Control': 'no-store' },
    });
  } catch {
    return NextResponse.json({ detail: 'Сервис рекомендаций недоступен. Попробуйте ещё раз.' }, { status: 503 });
  }
}
