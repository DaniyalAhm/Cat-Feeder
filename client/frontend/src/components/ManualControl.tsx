import { useEffect, useRef, useState } from 'react';
import { ApiError, postFeedNow } from '../api/client';

const COOLDOWN_MS = 1000;

export function ManualControl({
  onToast,
  onDone,
  feedDuration = 6,
}: {
  onToast: (msg: string) => void;
  onDone: () => void;
  feedDuration?: number;
}) {
  const [pending, setPending] = useState(false);
  const [phase, setPhase] = useState<'feeding' | 'cooldown' | null>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    const stash = timers.current;
    return () => {
      stash.forEach((t) => clearTimeout(t));
    };
  }, []);

  const lockForFeed = (durationS: number) => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
    // Lock covers the whole feed (~duration) + 1s cooldown after it finishes.
    setPhase('feeding');
    const feedMs = Math.max(0, durationS * 1000);
    timers.current.push(
      window.setTimeout(() => setPhase('cooldown'), feedMs),
      window.setTimeout(() => setPhase(null), feedMs + COOLDOWN_MS),
    );
  };

  const feed = async () => {
    if (pending || phase) return;
    setPending(true);
    try {
      await postFeedNow();
      onToast('Feed triggered');
      onDone();
      lockForFeed(feedDuration);
    } catch (e) {
      const msg = (e as Error).message;
      if (/busy/i.test(msg)) {
        onToast('Feed already running — wait for it to finish');
      } else if (e instanceof ApiError && /cooldown|429/i.test(msg)) {
        onToast('Wait 1s after the feed finishes');
      } else {
        onToast('Feed failed: ' + msg);
      }
    } finally {
      setPending(false);
    }
  };

  const disabled = pending || phase !== null;

  return (
    <section className="rounded-xl bg-white p-4 shadow dark:bg-zinc-900">
      <h2 className="mb-2 text-base font-semibold">Manual control</h2>
      <button
        type="button"
        onClick={feed}
        disabled={disabled}
        className="rounded-md bg-emerald-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {pending || phase === 'feeding' ? 'Feeding…' : phase === 'cooldown' ? 'Wait…' : 'Feed now'}
      </button>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Feed now runs one full cycle (run → wait → stop) in the background. Wait for it to
        finish plus 1s before feeding again.
      </p>
    </section>
  );
}
