import { useEffect, useState } from 'react';
import { postConfig, postStart, postStop } from '../api/client';
import type { FeederStatus } from '../api/types';
import { validateSchedule } from './validate';

interface Props {
  status: FeederStatus | null;
  onToast: (msg: string) => void;
  onSaved: () => void;
}

interface FormState {
  ip: string;
  port: string;
  mode: 'schedule' | 'interval';
  times: string[];
  interval: string;
  duration: string;
}

function fromStatus(s: FeederStatus | null): FormState {
  return {
    ip: s?.ip ?? '',
    port: String(s?.port ?? ''),
    mode: s?.mode ?? 'schedule',
    times: s && s.times.length ? [...s.times] : ['07:00'],
    interval: String(s?.interval ?? ''),
    duration: String(s?.duration ?? ''),
  };
}

const inputCls =
  'mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-base dark:border-zinc-700 dark:bg-zinc-800';

function suggestNext(times: string[]): string {
  if (!times.length) return '12:00';
  const last = times[times.length - 1];
  const m = /^(\d{1,2}):(\d{2})$/.exec(last);
  if (!m) return '12:00';
  const h = (Number(m[1]) + 1) % 24;
  return `${String(h).padStart(2, '0')}:${m[2]}`;
}

export function ScheduleForm({ status, onToast, onSaved }: Props) {
  const [values, setValues] = useState<FormState>(() => fromStatus(status));
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);

  // Echo backend state into the form until the user edits it.
  useEffect(() => {
    if (!dirty && status) setValues(fromStatus(status));
  }, [status, dirty]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => {
    setValues((prev) => ({ ...prev, [k]: v }));
    setDirty(true);
  };

  const setTime = (i: number, v: string) => {
    setValues((prev) => {
      const times = [...prev.times];
      times[i] = v;
      return { ...prev, times };
    });
    setDirty(true);
  };

  const addTime = () => {
    setValues((prev) => ({ ...prev, times: [...prev.times, suggestNext(prev.times)] }));
    setDirty(true);
  };

  const removeTime = (i: number) => {
    setValues((prev) => ({ ...prev, times: prev.times.filter((_, j) => j !== i) }));
    setDirty(true);
  };

  const applyPreset = (times: string[]) => {
    setValues((prev) => ({ ...prev, times }));
    setDirty(true);
  };

  const save = async () => {
    // De-dupe + sort for a stable schedule.
    const cleaned = [...new Set(values.times.map((t) => t.trim()).filter(Boolean))].sort();
    const err = validateSchedule({ ...values, times: cleaned });
    if (err) {
      setError(err);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await postConfig({
        ip: values.ip.trim(),
        port: Number(values.port),
        mode: values.mode,
        times: cleaned.join(','),
        interval: Number(values.interval),
        duration: Number(values.duration),
      });
      setValues((prev) => ({ ...prev, times: cleaned }));
      setDirty(false);
      onToast(`Saved ${cleaned.length === 1 ? '1 feeding time' : `${cleaned.length} feeding times`}`);
      onSaved();
    } catch (e) {
      onToast('Save failed: ' + (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (action: 'start' | 'stop') => {
    setToggling(true);
    try {
      if (action === 'start') {
        await postStart();
        onToast('Scheduler started');
      } else {
        await postStop();
        onToast('Scheduler stopped');
      }
      onSaved();
    } catch (e) {
      onToast(`${action === 'start' ? 'Start' : 'Stop'} failed: ` + (e as Error).message);
    } finally {
      setToggling(false);
    }
  };

  const isInterval = values.mode === 'interval';

  return (
    <section className="rounded-xl bg-white p-4 shadow dark:bg-zinc-900">
      <h2 className="mb-2 text-base font-semibold">Feed schedule</h2>

      <label htmlFor="cfg-mode" className="mb-2 block text-[0.95rem]">
        Mode
        <select
          id="cfg-mode"
          className={inputCls}
          value={values.mode}
          onChange={(e) => set('mode', e.target.value as FormState['mode'])}
        >
          <option value="schedule">Daily times</option>
          <option value="interval">Repeat every N seconds</option>
        </select>
      </label>

      <label htmlFor="cfg-ip" className="mb-2 block text-[0.95rem]">
        ESP32 STA IP
        <input
          id="cfg-ip"
          className={inputCls}
          inputMode="decimal"
          placeholder="10.0.0.128"
          value={values.ip}
          onChange={(e) => set('ip', e.target.value)}
        />
      </label>

      <label htmlFor="cfg-port" className="mb-2 block text-[0.95rem]">
        ESP32 port
        <input
          id="cfg-port"
          className={inputCls}
          type="number"
          min={1}
          max={65535}
          value={values.port}
          onChange={(e) => set('port', e.target.value)}
        />
      </label>

      {!isInterval ? (
        <fieldset className="mb-2">
          <legend className="text-[0.95rem]">Daily feeding times</legend>
          <div className="mt-1 flex flex-col gap-2">
            {values.times.map((t, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  aria-label={`Feeding time ${i + 1}`}
                  className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-base dark:border-zinc-700 dark:bg-zinc-800"
                  type="time"
                  value={t}
                  onChange={(e) => setTime(i, e.target.value)}
                />
                <button
                  type="button"
                  aria-label={`Remove time ${t || i + 1}`}
                  onClick={() => removeTime(i)}
                  className="shrink-0 rounded-md border border-zinc-300 px-3 py-1.5 text-lg leading-none dark:border-zinc-600"
                >
                  −
                </button>
              </div>
            ))}
          </div>
          {values.times.length === 0 && (
            <p className="mt-1 text-sm text-zinc-500">No times yet — add one below.</p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={addTime}
              className="rounded-md border border-zinc-400 bg-zinc-100 px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800"
            >
              + Add time
            </button>
            <button
              type="button"
              onClick={() => applyPreset(['07:00', '18:00'])}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600"
            >
              Morning + evening
            </button>
            <button
              type="button"
              onClick={() => applyPreset(['07:00', '12:30', '18:00'])}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600"
            >
              3× day
            </button>
          </div>
        </fieldset>
      ) : (
        <label htmlFor="cfg-interval" className="mb-2 block text-[0.95rem]">
          Repeat every (seconds)
          <input
            id="cfg-interval"
            className={inputCls}
            type="number"
            step={1}
            min={1}
            value={values.interval}
            onChange={(e) => set('interval', e.target.value)}
          />
        </label>
      )}

      <label htmlFor="cfg-duration" className="mb-2 block text-[0.95rem]">
        Motor-on seconds
        <input
          id="cfg-duration"
          className={inputCls}
          type="number"
          step={0.5}
          min={0.5}
          value={values.duration}
          onChange={(e) => set('duration', e.target.value)}
        />
      </label>

      {error && (
        <p role="alert" className="mb-2 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="rounded-md border border-zinc-400 bg-zinc-100 px-4 py-2 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-800"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          onClick={() => toggle('start')}
          disabled={toggling}
          className="rounded-md bg-emerald-600 px-4 py-2 text-white disabled:opacity-50"
        >
          Start
        </button>
        <button
          type="button"
          onClick={() => toggle('stop')}
          disabled={toggling}
          className="rounded-md bg-red-600 px-4 py-2 text-white disabled:opacity-50"
        >
          Stop
        </button>
      </div>
    </section>
  );
}
