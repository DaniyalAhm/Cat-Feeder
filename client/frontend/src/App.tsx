import { useCallback, useRef, useState } from 'react';
import { ConnectionPill } from './components/ConnectionPill';
import { EventLog } from './components/EventLog';
import { ManualControl } from './components/ManualControl';
import { ScheduleForm } from './components/ScheduleForm';
import { StatusCard } from './components/StatusCard';
import { Toast } from './components/Toast';
import { useFeeder } from './hooks/useFeeder';

export default function App() {
  const { status, events, conn, refresh } = useFeeder();
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3000);
  }, []);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 flex items-center gap-4 bg-zinc-900 px-4 py-3 text-white">
        <h1 className="m-0 text-lg">🐈 Cat-Feeding-Inator</h1>
        <ConnectionPill conn={conn} />
      </header>

      <main className="mx-auto flex max-w-[620px] flex-col gap-4 p-4">
        <StatusCard status={status} />
        <ScheduleForm status={status} onToast={showToast} onSaved={refresh} />
        <ManualControl onToast={showToast} onDone={refresh} />
        <EventLog events={events} />
      </main>

      <Toast msg={toast} />
    </div>
  );
}
