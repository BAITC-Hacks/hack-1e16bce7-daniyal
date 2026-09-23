'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { loadStarter, validate, type Dataset } from './model';
export const STORAGE_KEY = 'career-quest:unified:v2';

export function useCareer() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const latest = useRef<Dataset | null>(null);
  const accept = useCallback((d: Dataset) => { latest.current = d; setData(d); }, []);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      let cached: Dataset | null = null;
      try { const source = localStorage.getItem(STORAGE_KEY); if (source) { const value: unknown = JSON.parse(source); validate(value); cached = value; } }
      catch { setError('Сохранение браузера недоступно или повреждено. Загружен исходный набор; можно экспортировать изменения.'); }
      accept(cached || await loadStarter());
    } catch (e) { setError(e instanceof Error ? e.message : 'Ошибка загрузки. Повторите попытку.'); }
    finally { setLoading(false); }
  }, [accept]);
  useEffect(() => { void load(); const sync = (e: StorageEvent) => { if (e.key !== STORAGE_KEY || !e.newValue) return; try { const value: unknown = JSON.parse(e.newValue); validate(value); accept(value); setNotice('Данные обновлены из другой вкладки.'); } catch { setError('Не удалось прочитать обновление из другой вкладки.'); } }; window.addEventListener('storage', sync); return () => window.removeEventListener('storage', sync); }, [load, accept]);
  function change(update: Dataset | ((current: Dataset) => Dataset), message: string) {
    if (!latest.current) return false;
    try {
      const next = typeof update === 'function' ? update(latest.current) : update;
      validate(next); accept(next); setNotice(message); setError('');
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); }
      catch { setError('Изменения применены в этой вкладке. Браузер не сохранил их — скачайте резервную копию перед выходом.'); }
      return true;
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось применить изменение.'); return false; }
  }
  return { data, loading, error, notice, change, reload: load, setError, setNotice };
}
