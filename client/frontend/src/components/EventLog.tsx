export function EventLog({ events }: { events: string[] }) {
  return (
    <section className="rounded-xl bg-white p-4 shadow dark:bg-zinc-900">
      <h2 className="mb-2 text-base font-semibold">Events</h2>
      <pre className="max-h-[220px] overflow-y-auto rounded-md bg-zinc-950 p-2 text-[0.85rem] text-green-200">
        {events.length ? events.join('\n') : '–'}
      </pre>
    </section>
  );
}
