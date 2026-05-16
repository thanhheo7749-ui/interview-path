import { ArrowRight, CalendarCheck, CheckCircle2, FileInput, IdCard, Link2, Sparkles, Wand2, X } from 'lucide-react';

function ScoreRow({ label, value, tone = 'blue' }) {
  const bar = {
    blue: 'bg-blue-600',
    green: 'bg-emerald-600',
    purple: 'bg-violet-600',
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm font-semibold">
        <span className="text-slate-600">{label}</span>
        <span className="text-slate-950">{value}%</span>
      </div>
      <div className="h-2 rounded-full bg-slate-100">
        <div className={`h-2 rounded-full ${bar[tone]}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function CandidateDetailPanel({ candidate, onClose, onAction }) {
  if (!candidate) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-[420px] border-l border-slate-200 bg-white shadow-panel">
      <div className="flex h-full flex-col">
        <header className="border-b border-slate-200 p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-extrabold uppercase tracking-[0.18em] text-violet-500">Candidate Passport</p>
              <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">{candidate.name}</h2>
              <p className="mt-1 text-sm font-semibold text-slate-500">{candidate.role}</p>
              <div className="mt-3 flex items-center gap-2">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-extrabold text-slate-600">{candidate.passportId}</span>
                {candidate.hasNewReport ? (
                  <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-extrabold text-blue-700">New AI Report</span>
                ) : null}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close candidate detail panel"
              className="rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-950"
            >
              <X size={20} />
            </button>
          </div>
          <div className="mt-5 flex items-center gap-3 rounded-2xl bg-slate-950 p-4 text-white">
            <IdCard className="text-emerald-300" size={24} />
            <p className="text-sm font-semibold leading-6">
              InterviewPath stores readiness, feedback, and hiring history across the full recruitment journey.
            </p>
          </div>
        </header>

        <div className="thin-scrollbar flex-1 space-y-6 overflow-y-auto p-6">
          <section className="rounded-2xl border border-slate-200 p-5">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-sm font-extrabold text-slate-950">Memory completeness</p>
                <p className="mt-1 text-sm font-semibold text-slate-500">{candidate.readinessTrend}</p>
              </div>
              <p className="text-3xl font-extrabold tracking-tight text-slate-950">{candidate.memoryCompleteness}%</p>
            </div>
            <div className="mt-4 h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-blue-600" style={{ width: `${candidate.memoryCompleteness}%` }} />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {candidate.evidence.map((item) => (
                <span key={item} className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-extrabold text-slate-600">
                  {item}
                </span>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-blue-100 bg-blue-50 p-5">
            <p className="flex items-center gap-2 text-sm font-extrabold text-blue-900">
              <Sparkles size={18} />
              AI hiring insight
            </p>
            <p className="mt-2 text-sm font-semibold leading-6 text-blue-950">{candidate.aiInsight}</p>
          </section>

          <section className="rounded-2xl border border-violet-100 bg-violet-50 p-5">
            <p className="text-sm font-extrabold text-violet-900">Why AI recommends this next action</p>
            <p className="mt-2 text-sm font-semibold leading-6 text-violet-950">{candidate.recommendationReason}</p>
          </section>

          <section className="space-y-4 rounded-2xl border border-slate-200 p-5">
            <ScoreRow label="Technical fit" value={candidate.technicalFit} tone="blue" />
            <ScoreRow label="English readiness" value={candidate.englishReadiness} tone="purple" />
            <ScoreRow label="Culture fit" value={candidate.cultureFit} tone="green" />
          </section>

          <section>
            <p className="text-sm font-extrabold text-slate-950">Skills memory</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {candidate.skills.map((skill) => (
                <span key={skill} className="rounded-full bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700">
                  {skill}
                </span>
              ))}
            </div>
          </section>

          <section>
            <p className="text-sm font-extrabold text-slate-950">Passport timeline</p>
            <div className="mt-3 space-y-3">
              {candidate.passportEvents.map((event, index) => (
                <TimelineItem key={`${event.label}-${index}`} event={event} isLast={index === candidate.passportEvents.length - 1} />
              ))}
            </div>
          </section>
        </div>

        <footer className="border-t border-slate-200 p-6">
          <div className="mb-4 grid grid-cols-3 gap-2">
            <ActionButton icon={Link2} label="Send Practice" onClick={() => onAction(candidate, 'practice')} />
            <ActionButton icon={Wand2} label="Generate Passport" onClick={() => onAction(candidate, 'passport')} />
            <ActionButton icon={ArrowRight} label="Technical Round" onClick={() => onAction(candidate, 'technical')} />
          </div>
          <button
            type="button"
            onClick={() => onAction(candidate, 'report')}
            className="mb-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-extrabold text-blue-800 transition hover:bg-blue-100"
          >
            <FileInput size={18} />
            Import Latest Interview Report
          </button>
          <div className="rounded-2xl bg-emerald-50 p-4">
            <p className="flex items-center gap-2 text-sm font-extrabold text-emerald-800">
              <CalendarCheck size={18} />
              Recommended next action
            </p>
            <p className="mt-2 text-sm font-semibold leading-6 text-emerald-900">{candidate.nextAction}</p>
          </div>
        </footer>
      </div>
    </div>
  );
}

function TimelineItem({ event, isLast }) {
  const tone = {
    blue: 'bg-blue-600 ring-blue-100',
    green: 'bg-emerald-600 ring-emerald-100',
    purple: 'bg-violet-600 ring-violet-100',
  }[event.tone || 'blue'];

  return (
    <div className="relative flex gap-3">
      <div className="flex flex-col items-center">
        <div className={`mt-1 flex h-8 w-8 items-center justify-center rounded-full text-white ring-4 ${tone}`}>
          <CheckCircle2 size={16} />
        </div>
        {!isLast ? <div className="mt-2 h-full min-h-8 w-px bg-slate-200" /> : null}
      </div>
      <div className="flex-1 rounded-2xl bg-slate-50 p-3">
        <p className="text-sm font-extrabold text-slate-950">{event.label}</p>
        <p className="mt-1 text-sm font-medium leading-6 text-slate-600">{event.detail}</p>
      </div>
    </div>
  );
}

function ActionButton({ icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[76px] flex-col items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-2 py-3 text-center text-[11px] font-extrabold leading-4 text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800"
    >
      <Icon size={18} />
      {label}
    </button>
  );
}

export default CandidateDetailPanel;
