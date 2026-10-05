import { useCallback, useEffect, useRef, useState } from 'react';
import { getEvents, getStatus } from '../api/client';
import type { FeederStatus } from '../api/types';

export type ConnState = 'connecting' | 'connected' | 'unreachable';

const BASE_DELAY = 3000;
const MAX_DELAY = 15000;

export function useFeeder() {
  const [status, setStatus] = useState<FeederStatus | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [conn, setConn] = useState<ConnState>('connecting');
  const timer = useRef<number | null>(null);
  const inflight = useRef<AbortController | null>(null);
  const failures = useRef(0);

  const tick = useCallback(async () => {
    inflight.current?.abort();
    const ctl = new AbortController();
    inflight.current = ctl;
    try {
      const s = await getStatus(ctl.signal);
      // Events are best-effort; keep old log on failure.
      try {
        const e = await getEvents(ctl.signal);
        setEvents(e.events);
      } catch {
        /* keep old */
      }
      setStatus(s);
      setConn('connected');
      failures.current = 0;
      return BASE_DELAY;
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return BASE_DELAY;
      failures.current += 1;
      setConn(failures.current === 1 && status ? 'connected' : 'unreachable');
      if (failures.current > 1 || !status) setConn('unreachable');
      return Math.min(BASE_DELAY * 2 ** failures.current, MAX_DELAY);
    }
  }, [status]);

  const tickRef = useRef(tick);
  tickRef.current = tick;

  useEffect(() => {
    let stopped = false;
    const loop = async () => {
      const delay = await tickRef.current();
      if (!stopped) timer.current = window.setTimeout(loop, delay);
    };
    loop();
    return () => {
      stopped = true;
      if (timer.current) clearTimeout(timer.current);
      inflight.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refresh = useCallback(async () => {
    const delay = await tickRef.current();
    void delay;
  }, []);

  return { status, events, conn, refresh };
}
