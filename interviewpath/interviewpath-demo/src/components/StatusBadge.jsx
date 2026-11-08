// One color per lifecycle stage, reused everywhere a status is shown, so color alone tells the stage.
const STATUS_TONE = {
  draft: 'bg-slate-100 text-slate-600',
  closed: 'bg-slate-100 text-slate-600',
  withdrawn: 'bg-slate-100 text-slate-600',
  queued: 'bg-amber-100 text-amber-900',
  processing: 'bg-amber-100 text-amber-900',
  running: 'bg-amber-100 text-amber-900',
  review: 'bg-amber-100 text-amber-900',
  manager_review: 'bg-amber-100 text-amber-900',
  open: 'bg-amber-100 text-amber-900',
  intake_in_progress: 'bg-amber-100 text-amber-900',
  intake_done: 'bg-amber-100 text-amber-900',
  drafting: 'bg-amber-100 text-amber-900',
  intake_empty: 'bg-amber-100 text-amber-900',
  published: 'bg-emerald-100 text-emerald-800',
  approved: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-rose-100 text-rose-800',
  cancelled: 'bg-rose-100 text-rose-800',
};

function StatusBadge({ status, children }) {
  const tone = STATUS_TONE[status] ?? 'bg-slate-100 text-slate-600';
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] ${tone}`}>
      {children}
    </span>
  );
}

export default StatusBadge;
