import { useState } from 'react';
import { postFeedNow } from '../api/client';

export function ManualControl({
  onToast,
  onDone,
}: {
  onToast: (msg: string) => void;
  onDone: () => void;
}) {
  const [pending, setPending] = useState(false);

  const feed = async () => {
    setPending(true);
    try {
      await postFeedNow();
      onToast('Feed triggered');
      onDone();
    } catch (e) {
      onToast('Feed failed: ' + (e as Error).message);
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="rounded-xl bg-white p-4 shadow dark:bg-zinc-900">
      <h2 className="mb-2 text-base font-semibold">Manual control</h2>
      <button
        type="button"
        onClick={feed}
        disabled={pending}
        className="rounded-md bg-emerald-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {pending ? 'Feeding…' : 'Feed now'}
      </button>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Feed now runs one full cycle (run → wait → stop) in the background.
      </p>
    </section>
  );
}
