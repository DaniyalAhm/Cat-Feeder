import type { ConfigPayload, FeederStatus } from './types';

// Base override for prod when frontend/backend are on different origins.
// e.g. VITE_API_URL=http://localhost:6607 npm run build
// Dev ('' ): same-origin /api via the Vite proxy.
// Prod default: same hostname, backend port (backend sends CORS *),
// so http://toddheadquarters:6606 talks to http://toddheadquarters:6607.
const BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ??
  (import.meta.env.DEV ? '' : `http://${window.location.hostname}:6607`);
const API = `${BASE}/api`;

export class ApiError extends Error {}

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const r = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError((body as { error?: string }).error || `HTTP ${r.status}`);
  return body as T;
}

export const getStatus = (signal?: AbortSignal) =>
  api<FeederStatus>('/status', { signal });

export const getEvents = (signal?: AbortSignal) =>
  api<{ events: string[] }>('/events', { signal });

export const postConfig = (cfg: ConfigPayload) =>
  api<{ ok: boolean }>('/config', { method: 'POST', body: JSON.stringify(cfg) });

export const postStart = () => api<{ ok: boolean }>('/start', { method: 'POST' });
export const postStop = () => api<{ ok: boolean }>('/stop', { method: 'POST' });
export const postFeedNow = () => api<{ ok: boolean }>('/feed-now', { method: 'POST' });
