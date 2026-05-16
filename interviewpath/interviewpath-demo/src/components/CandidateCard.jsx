import { BadgeCheck, GripVertical, IdCard, Sparkles } from 'lucide-react';
import { useDraggable } from '@dnd-kit/core';

function CandidateCard({ candidate, onClick }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: candidate.id,
  });

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      }
    : undefined;

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={[
        'group rounded-2xl border border-slate-200 bg-white p-4 shadow-card transition',
        isDragging ? 'z-50 scale-[1.02] opacity-80 ring-2 ring-blue-300' : 'hover:-translate-y-0.5 hover:border-blue-200',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-3">
        <button type="button" onClick={onClick} className="min-w-0 flex-1 text-left">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-extrabold text-slate-950">{candidate.name}</p>
            <BadgeCheck size={15} className="shrink-0 text-emerald-500" />
          </div>
          <p className="mt-1 text-xs font-semibold text-slate-500">{candidate.role}</p>
        </button>
        <button
          type="button"
          aria-label={`Drag ${candidate.name}`}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          {...listeners}
          {...attributes}
        >
          <GripVertical size={17} />
        </button>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-extrabold text-emerald-700">
          {candidate.matchScore}% match
        </span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">{candidate.status}</span>
      </div>

      <div className="mt-4 rounded-xl bg-slate-50 p-3">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-400">Main skill</p>
        <p className="mt-1 text-sm font-bold text-slate-800">{candidate.skills[0]}</p>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs font-semibold text-slate-500">
        <span className="flex items-center gap-1.5">
          <IdCard size={15} className="text-violet-500" />
          Passport ready
        </span>
        <span className="flex items-center gap-1 text-blue-600">
          <Sparkles size={14} />
          AI memory
        </span>
      </div>
    </article>
  );
}

export default CandidateCard;
