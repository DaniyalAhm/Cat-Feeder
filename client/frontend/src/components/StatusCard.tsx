import type { FeederStatus } from '../api/types';

function motorLabel(s: FeederStatus): string {
  if (s.esp == null) return 'unreachable';
  return s.esp.motor_running ? 'ON' : 'off';
}

function planLabel(s: FeederStatus): string {
  if (s.mode === 'interval') return `every ${s.interval}s × ${s.duration}s`;
  return s.times.length ? s.times.join(', ') : '–';
}

export function StatusCard({ status }: { status: FeederStatus | null }) {
  const rows: Array<[string, string]> = status
    ? [
        ['Scheduler', status.running ? '▶ running' : '⏸ stopped'],
        ['Next feed', status.next || '–'],
        ['Last feed', status.last || '–'],
        ['Motor (ESP32)', motorLabel(status)],
        ['Target', `${status.ip}:${status.port}`],
        ['Plan', planLabel(status)],
      ]
    : [
        ['Scheduler', '–'],
        ['Next feed', '–'],
        ['Last feed', '–'],
        ['Motor (ESP32)', '–'],
        ['Target', '–'],
        ['Plan', '–'],
      ];

  return (
    <section className="rounded-xl bg-white p-4 shadow dark:bg-zinc-900">
      <h2 className="mb-2 text-base font-semibold">Status</h2>
      <div className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="text-[0.95rem]">
            {k} <strong>{v}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
