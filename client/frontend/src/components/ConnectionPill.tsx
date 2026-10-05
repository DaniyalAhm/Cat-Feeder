import type { ConnState } from '../hooks/useFeeder';

const styles: Record<ConnState, string> = {
  connecting: 'bg-zinc-500',
  connected: 'bg-emerald-600',
  unreachable: 'bg-red-600',
};

const labels: Record<ConnState, string> = {
  connecting: 'connecting…',
  connected: 'connected',
  unreachable: 'backend unreachable',
};

export function ConnectionPill({ conn }: { conn: ConnState }) {
  return (
    <span
      aria-live="polite"
      className={`rounded-full px-3 py-1 text-sm text-white ${styles[conn]}`}
    >
      {labels[conn]}
    </span>
  );
}
