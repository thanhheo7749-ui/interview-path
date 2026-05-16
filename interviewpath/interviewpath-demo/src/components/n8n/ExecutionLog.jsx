import { Terminal } from 'lucide-react';

function ExecutionLog({ logs }) {
  const visibleLogs = logs.slice(-2);
  const shouldRoll = visibleLogs.length > 1;

  return (
    <section className="h-full rounded-2xl border border-slate-200 bg-slate-950 p-3 text-white shadow-card">
      <div className="flex items-center justify-between gap-4">
        <p className="flex items-center gap-2 text-sm font-extrabold">
          <Terminal size={17} className="text-emerald-300" />
          Execution Log
        </p>
        <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-bold text-slate-300">{logs.length} events</span>
      </div>

      <div className="mt-2 h-10 overflow-hidden rounded-xl bg-slate-900 px-3">
        {visibleLogs.length ? (
          <div key={logs.length} className={shouldRoll ? 'log-stack-roll' : 'log-roll-up'}>
            {visibleLogs.map((log) => (
              <p key={`${log.time}-${log.message}`} className="flex h-10 items-center font-mono text-xs text-emerald-100">
                <span className="mr-2 text-slate-400">[{log.time}]</span>
                <span className="truncate">{log.message}</span>
              </p>
            ))}
          </div>
        ) : (
          <div className="flex h-10 items-center text-sm font-semibold text-slate-500">
            Run the workflow to stream n8n-style execution events.
          </div>
        )}
      </div>
    </section>
  );
}

export default ExecutionLog;
