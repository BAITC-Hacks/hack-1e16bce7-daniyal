export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

function errorMessage(body: unknown, status: number): string {
  if (status === 401) return 'Сессия завершена. Войдите снова.';
  if (status === 403) return 'У вашей роли нет доступа к этому действию.';
  if (status === 404) return 'Данные или маршрут API не найдены. Проверьте ID и подключение бизнес-API.';
  if (status >= 500) return 'Сервис временно недоступен. Попробуйте ещё раз.';
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = body.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((item: { loc?: unknown[]; msg?: string }) => `${item.loc?.join(' → ') || 'Данные'}: ${item.msg || 'Ошибка валидации'}`).join('\n');
  }
  return `Не удалось выполнить запрос (${status}).`;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), path === 'datasets/import' ? 60000 : 15000);
  const signal = options.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal;
  try {
    const response = await fetch(`/api/v1/${path}`, { ...options, signal, cache: 'no-store', credentials: 'same-origin' });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && path.startsWith('auth/demo/')) throw new ApiError('Не удалось войти. Проверьте данные для входа.', 401);
      if (response.status === 401) window.dispatchEvent(new Event('cq:unauthorized'));
      throw new ApiError(errorMessage(body, response.status), response.status);
    }
    if (body === null) throw new ApiError('Сервис вернул некорректный ответ.', 502);
    return normalizeEmployeeResponse(path, body) as T;
  } catch (error) {
    if (error instanceof ApiError || options.signal?.aborted) throw error;
    throw new ApiError(controller.signal.aborted ? 'Время ожидания истекло. Повторите запрос.' : 'Не удалось связаться с сервисом. Проверьте подключение.', 503);
  } finally { clearTimeout(timeout); }
}

// Adapt the existing FastAPI read contracts, without calculating any domain values.
function normalizeEmployeeResponse(path: string, body: unknown): unknown {
  if (!body || typeof body !== 'object') return body;
  if (/^employees\/[^/]+$/.test(path)) return { ...body, career_readiness: null };
  if (/^employees\/[^/]+\/skills$/.test(path) && 'items' in body && Array.isArray(body.items)) {
    return body.items.map((skill: { skill_id: string; name: string; level: number }) => ({ skill_id: skill.skill_id, name: skill.name, current_level: skill.level, required_level: null }));
  }
  if (/^employees\/[^/]+\/activities(?:\?|$)/.test(path) && 'items' in body && Array.isArray(body.items)) {
    return { ...body, items: body.items.map((activity: { event_title: string }) => ({ ...activity, title: activity.event_title })) };
  }
  return body;
}

export const jsonPost = (value: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
export const employeePath = (id: string) => `employees/${encodeURIComponent(id)}`;
export const message = (error: unknown) => error instanceof Error ? error.message : 'Не удалось выполнить действие.';
export const percent = (value: number | null) => value === null ? 'Нет данных' : `${value}%`;
export const dateLabel = (value: string) => new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
