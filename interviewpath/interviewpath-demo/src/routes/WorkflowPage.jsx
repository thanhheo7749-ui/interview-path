import { DndContext, useDroppable } from '@dnd-kit/core';
import { CalendarDays, DatabaseZap, Star, Users } from 'lucide-react';
import { useMemo, useState } from 'react';
import CandidateCard from '../components/CandidateCard.jsx';
import CandidateDetailPanel from '../components/CandidateDetailPanel.jsx';
import MetricCard from '../components/MetricCard.jsx';
import Toast from '../components/Toast.jsx';
import { initialCandidates, stages } from '../data/mockCandidates.js';

function WorkflowPage() {
  const [candidates, setCandidates] = useState(initialCandidates);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [toast, setToast] = useState('');

  const metrics = useMemo(() => {
    const total = candidates.length;
    const average = Math.round(candidates.reduce((sum, item) => sum + item.matchScore, 0) / total);
    const scheduled = candidates.filter((item) => ['Scheduled', 'Technical Round', 'Culture Round'].includes(item.stage)).length;
    const pool = candidates.filter((item) => item.stage === 'Hired / Talent Pool').length;
    return { total, average, scheduled, pool };
  }, [candidates]);

  function handleDragEnd(event) {
    const { active, over } = event;
    if (!over) return;
    setCandidates((current) =>
      current.map((candidate) => (candidate.id === active.id ? { ...candidate, stage: over.id } : candidate)),
    );
  }

  function showToast(message) {
    setToast(message);
    setTimeout(() => setToast(''), 2600);
  }

  function updateCandidate(candidateId, updater, message) {
    setCandidates((current) => {
      const next = current.map((candidate) => (candidate.id === candidateId ? updater(candidate) : candidate));
      const updated = next.find((candidate) => candidate.id === candidateId);
      setSelectedCandidate(updated);
      return next;
    });
    showToast(message);
  }

  function handleAction(candidate, action) {
    const actions = {
      practice: {
        message: `AI practice link sent to ${candidate.name}.`,
        update: (item) => ({
          ...item,
          stage: 'Practice Sent',
          status: 'Practice sent',
          nextAction: 'Wait for AI practice completion',
          interviewHistory: [...item.interviewHistory, 'AI practice link sent'],
          passportEvents: [
            ...item.passportEvents,
            { label: 'Practice link sent', detail: 'Candidate received a simulated AI interview practice link.', tone: 'purple' },
          ],
        }),
      },
      passport: {
        message: `Candidate Passport generated for ${candidate.name}.`,
        update: (item) => ({
          ...item,
          status: 'Passport updated',
          aiInsight: `${item.aiInsight} Passport refreshed with the latest HR action and readiness signal.`,
          interviewHistory: [...item.interviewHistory, 'Candidate Passport generated'],
          passportEvents: [
            ...item.passportEvents,
            { label: 'Passport generated', detail: 'Readiness, feedback, and hiring history merged into one HR view.', tone: 'green' },
          ],
        }),
      },
      technical: {
        message: `${candidate.name} moved to Technical Round.`,
        update: (item) => ({
          ...item,
          stage: 'Technical Round',
          status: 'Technical round',
          nextAction: 'Prepare role-specific technical questions',
          interviewHistory: [...item.interviewHistory, 'Moved to technical round'],
          passportEvents: [
            ...item.passportEvents,
            { label: 'Moved to technical round', detail: 'HR accepted AI readiness signal and advanced the candidate.', tone: 'blue' },
          ],
        }),
      },
      report: {
        message: `Latest AI interview report imported for ${candidate.name}.`,
        update: (item) => ({
          ...item,
          hasNewReport: true,
          status: 'New AI report',
          stage: item.stage === 'Shortlisted' ? 'Practice Sent' : item.stage,
          memoryCompleteness: Math.min(98, item.memoryCompleteness + 7),
          readinessTrend: '+12% after imported interview report',
          evidence: Array.from(new Set([...item.evidence, 'AI Interview Report'])),
          aiInsight:
            'New AI interview report received. English clarity is 78%, technical relevance is 84%, and culture fit is 81%. Proceed to technical round.',
          nextAction: 'Review AI report and proceed to technical round',
          interviewHistory: [...item.interviewHistory, 'Latest AI interview report imported from candidate room'],
          passportEvents: [
            ...item.passportEvents,
            {
              label: 'Interview report imported',
              detail: 'Candidate room summary was added to the HR Candidate Passport.',
              tone: 'green',
            },
          ],
        }),
      },
    };

    updateCandidate(candidate.id, actions[action].update, actions[action].message);
  }

  return (
    <div className="min-h-[100dvh] p-6">
      <Toast message={toast} />
      <header className="mb-5 flex items-start justify-between gap-6">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-blue-600">HR Workspace</p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-950">Recruitment Pipeline</h1>
          <p className="mt-2 max-w-3xl text-sm font-medium leading-6 text-slate-600">
            InterviewPath does not stop at interview practice. It creates an AI Candidate Passport that stores candidate readiness,
            feedback, and hiring history across the full recruitment journey.
          </p>
        </div>
      </header>

      <section className="mb-5 grid grid-cols-4 gap-4">
        <MetricCard label="Total candidates" value={metrics.total} helper="Across all active stages" icon={Users} tone="blue" />
        <MetricCard label="Average match score" value={`${metrics.average}%`} helper="Weighted by current shortlist" icon={Star} tone="green" />
        <MetricCard label="Interviews scheduled" value={metrics.scheduled} helper="Live or pending rounds" icon={CalendarDays} tone="purple" />
        <MetricCard label="Talent pool count" value={metrics.pool} helper="Reusable hiring memory" icon={DatabaseZap} tone="slate" />
      </section>

      <DndContext onDragEnd={handleDragEnd}>
        <section className="thin-scrollbar flex gap-4 overflow-x-auto pb-3">
          {stages.map((stage) => (
            <PipelineColumn
              key={stage}
              stage={stage}
              candidates={candidates.filter((candidate) => candidate.stage === stage)}
              onSelect={setSelectedCandidate}
            />
          ))}
        </section>
      </DndContext>

      <CandidateDetailPanel
        candidate={selectedCandidate}
        onClose={() => setSelectedCandidate(null)}
        onAction={handleAction}
      />
    </div>
  );
}

function PipelineColumn({ stage, candidates, onSelect }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });

  return (
    <div
      ref={setNodeRef}
      className={[
        'min-h-[430px] w-[252px] shrink-0 rounded-3xl border p-3 transition',
        isOver ? 'border-blue-300 bg-blue-50' : 'border-slate-200 bg-slate-50',
      ].join(' ')}
    >
      <div className="mb-3 flex items-center justify-between px-1">
        <h2 className="text-sm font-extrabold text-slate-800">{stage}</h2>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-500 shadow-sm">{candidates.length}</span>
      </div>
      <div className="space-y-3">
        {candidates.map((candidate) => (
          <CandidateCard key={candidate.id} candidate={candidate} onClick={() => onSelect(candidate)} />
        ))}
      </div>
      {candidates.length === 0 ? (
        <div className="mt-3 rounded-2xl border border-dashed border-slate-300 bg-white p-5 text-center text-xs font-bold text-slate-400">
          Drop candidates here
        </div>
      ) : null}
    </div>
  );
}

export default WorkflowPage;
