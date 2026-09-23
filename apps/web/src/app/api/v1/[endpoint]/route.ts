import { NextResponse } from 'next/server';

// Fixed allowlist: this is a system-status proxy, not an arbitrary URL proxy.
export async function GET(_request: Request, context: { params: Promise<{ endpoint: string }> }) {
  const { endpoint } = await context.params;
  if (!['health', 'ready'].includes(endpoint)) {
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
