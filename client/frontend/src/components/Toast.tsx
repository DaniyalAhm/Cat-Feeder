export function Toast({ msg }: { msg: string | null }) {
  if (!msg) return null;
  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-lg bg-zinc-900 px-5 py-2.5 text-white shadow dark:bg-zinc-100 dark:text-zinc-900"
    >
      {msg}
    </div>
  );
}
