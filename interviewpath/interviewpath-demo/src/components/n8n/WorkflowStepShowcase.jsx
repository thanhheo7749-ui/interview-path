import {
  ArrowRight,
  Bot,
  Braces,
  CalendarCheck,
  CheckCircle2,
  Database,
  FileText,
  Gauge,
  IdCard,
  Mail,
  Send,
  UserRound,
} from 'lucide-react';

function WorkflowStepShowcase({ node, stepLabel }) {
  if (!node) {
    return (
      <aside className="flex h-full flex-col rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
        <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
          <Gauge size={32} className="text-slate-400" />
          <p className="mt-3 text-sm font-extrabold text-slate-700">Ready for presentation mode</p>
          <p className="mt-2 text-sm font-medium leading-6 text-slate-500">
            Press Next Step to spotlight each automation node with a live visual story.
          </p>
        </div>
      </aside>
    );
  }

  const data = node.data;
  const story = data.story || {};

  return (
    <aside className="thin-scrollbar h-full overflow-y-auto rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
      <div className="workflow-presenter-panel">
        <div key={data.id} className="story-visual-frame">
          <StoryVisual story={story} data={data} />
        </div>

        <div className="mt-5 grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3">
          <FlowPill label="Input" />
          <ArrowRight size={14} className="text-slate-400" />
          <FlowPill label="Process" tone="blue" />
          <ArrowRight size={14} className="text-slate-400" />
          <FlowPill label="Output" tone="green" />
        </div>

        <div className="mt-4 space-y-3">
          <DetailBlock title="Input data" value={data.input} />
          <DetailBlock title="Processing logic" value={data.process} />
          <DetailBlock title="Output data" value={data.output} />
        </div>

        <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
          <div className="flex items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-sm font-extrabold text-slate-950">
              <Braces size={17} className="text-blue-600" />
              Live payload
            </p>
            <span className="rounded-full bg-slate-950 px-2.5 py-1 text-[10px] font-black uppercase text-white">
              {stepLabel.includes('Step') ? 'JSON' : 'Ready'}
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {(story.payloadPreview || []).map(([label, value]) => (
              <div key={label} className="grid grid-cols-[92px_minmax(0,1fr)] gap-3 rounded-xl bg-slate-50 px-3 py-2 text-xs">
                <span className="font-extrabold text-slate-500">{label}</span>
                <span className="min-w-0 text-right font-bold leading-5 text-slate-900">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}

function StoryVisual({ story, data }) {
  switch (story.visual) {
    case 'extract-data':
      return <ExtractDataVisual story={story} />;
    case 'match-score':
      return <MatchScoreVisual story={story} />;
    case 'passport-build':
      return <PassportBuildVisual story={story} />;
    case 'practice-link':
      return <PracticeLinkVisual story={story} />;
    case 'interview-feedback':
      return <InterviewFeedbackVisual story={story} />;
    case 'schedule-slot':
      return <ScheduleSlotVisual story={story} />;
    case 'hr-dashboard':
      return <HrDashboardVisual story={story} />;
    case 'memory-save':
      return <MemorySaveVisual story={story} />;
    case 'cv-intake':
    default:
      return <CvIntakeVisual story={story} data={data} />;
  }
}

function CvIntakeVisual({ story, data }) {
  return (
    <div className="story-stage story-stage-cv">
      <div className="story-orbit story-orbit-left" />
      <div className="story-cv-card story-fly-in">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-600 text-white">
            <UserRound size={22} />
          </div>
          <div>
            <p className="text-sm font-extrabold text-slate-950">{data.jsonPayload.candidateName}</p>
            <p className="text-xs font-bold text-slate-500">{data.jsonPayload.targetRole}</p>
          </div>
        </div>
        <div className="mt-4 space-y-2">
          <div className="h-2.5 w-full rounded-full bg-slate-200" />
          <div className="h-2.5 w-4/5 rounded-full bg-slate-200" />
          <div className="h-2.5 w-2/3 rounded-full bg-slate-200" />
        </div>
        <div className="story-artifact-pill mt-4 flex items-center gap-2 rounded-xl bg-blue-50 px-3 py-2 text-xs font-extrabold text-blue-700">
          <FileText size={14} />
          <span>{story.artifact}</span>
        </div>
      </div>
      <div className="story-drop-zone">
        <Mail size={22} />
        <span>Career Form</span>
      </div>
    </div>
  );
}

function ExtractDataVisual({ story }) {
  return (
    <div className="story-stage story-stage-extract">
      <div className="story-document">
        <div className="h-3 w-24 rounded-full bg-slate-300" />
        <div className="mt-5 space-y-3">
          <div className="h-2 rounded-full bg-slate-200" />
          <div className="h-2 w-5/6 rounded-full bg-slate-200" />
          <div className="h-2 w-3/4 rounded-full bg-slate-200" />
          <div className="h-2 w-4/5 rounded-full bg-slate-200" />
        </div>
        <div className="scan-beam" />
      </div>
      <div className="story-chip-cloud">
        {story.chips.map((chip, index) => (
          <span key={chip} className="story-chip" style={{ animationDelay: `${index * 110}ms` }}>
            {chip}
          </span>
        ))}
      </div>
    </div>
  );
}

function MatchScoreVisual({ story }) {
  return (
    <div className="story-stage story-stage-match">
      <div className="story-jd-card">
        <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-slate-500">JD Requirements</p>
        {['Java', 'Spring Boot', 'SQL', 'Communication'].map((item) => (
          <div key={item} className="mt-2 flex items-center gap-2 text-xs font-bold text-slate-700">
            <CheckCircle2 size={14} className="text-emerald-600" />
            {item}
          </div>
        ))}
      </div>
      <div className="score-ring" style={{ '--score': '92%' }}>
        <div>
          <p className="text-3xl font-black text-white">92%</p>
          <p className="text-xs font-extrabold text-blue-100">Match</p>
        </div>
      </div>
      <div className="story-match-lines">
        {story.chips.slice(0, 3).map((chip, index) => (
          <span key={chip} style={{ animationDelay: `${index * 120}ms` }}>
            {chip}
          </span>
        ))}
      </div>
    </div>
  );
}

function PassportBuildVisual({ story }) {
  return (
    <div className="story-stage story-stage-passport">
      <div className="passport-card">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-600 text-white">
            <IdCard size={24} />
          </div>
          <div>
            <p className="text-sm font-black text-slate-950">{story.artifact}</p>
            <p className="text-xs font-bold text-slate-500">Candidate Passport</p>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2">
          {story.chips.map((chip, index) => (
            <span key={chip} className="passport-chip" style={{ animationDelay: `${index * 120}ms` }}>
              {chip}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function PracticeLinkVisual({ story }) {
  return (
    <div className="story-stage story-stage-practice">
      <div className="link-token">
        <span>{story.artifact}</span>
      </div>
      <Send className="paper-plane" size={34} />
      <div className="message-card">
        <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-indigo-600">Practice Invite</p>
        <p className="mt-2 text-sm font-black text-slate-950">Candidate Interview Link</p>
        <p className="mt-1 text-xs font-bold text-slate-500">candidate@demo.com</p>
      </div>
    </div>
  );
}

function InterviewFeedbackVisual({ story }) {
  return (
    <div className="story-stage story-stage-feedback">
      <div className="chat-bubble ai">
        <Bot size={16} />
        <span>Explain your API design tradeoff.</span>
      </div>
      <div className="chat-bubble candidate">
        <UserRound size={16} />
        <span>I used Spring Boot with PostgreSQL...</span>
      </div>
      <div className="score-bars">
        {story.chips.map((chip, index) => (
          <div key={chip} className="score-row">
            <span>{chip}</span>
            <div>
              <i style={{ width: `${78 + index * 2}%`, animationDelay: `${index * 130}ms` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScheduleSlotVisual({ story }) {
  return (
    <div className="story-stage story-stage-schedule">
      <div className="calendar-card">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-black text-slate-950">Technical Round</p>
          <CalendarCheck size={20} className="text-cyan-600" />
        </div>
        <div className="grid grid-cols-3 gap-2">
          {['09:00', '09:30', '10:00', '10:30', '11:00', '14:00'].map((slot) => (
            <span key={slot} className={slot === '10:00' ? 'slot selected' : 'slot'}>
              {slot}
            </span>
          ))}
        </div>
        <p className="mt-4 rounded-xl bg-cyan-50 px-3 py-2 text-xs font-extrabold text-cyan-700">{story.artifact}</p>
      </div>
    </div>
  );
}

function HrDashboardVisual({ story }) {
  return (
    <div className="story-stage story-stage-dashboard">
      <div className="dashboard-preview">
        <div className="flex items-center justify-between">
          <p className="text-sm font-black text-slate-950">HR Pipeline</p>
          <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-black text-emerald-700">{story.artifact}</span>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          {['Screening', 'Technical', 'Offer'].map((stage) => (
            <div key={stage} className={stage === 'Technical' ? 'pipeline-stage active' : 'pipeline-stage'}>
              {stage}
            </div>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Metric label="Match" value="92%" />
          <Metric label="Readiness" value="82%" />
        </div>
      </div>
    </div>
  );
}

function MemorySaveVisual({ story }) {
  return (
    <div className="story-stage story-stage-memory">
      <div className="memory-card">
        <IdCard size={18} />
        <span>IP-2026-BE-092</span>
      </div>
      <div className="database-vault">
        <Database size={36} />
        <span>{story.artifact}</span>
      </div>
      <div className="memory-graph">
        <i />
        <i />
        <i />
        <i />
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-black text-slate-950">{value}</p>
    </div>
  );
}

function FlowPill({ label, tone = 'slate' }) {
  const className =
    tone === 'blue'
      ? 'bg-blue-50 text-blue-700'
      : tone === 'green'
        ? 'bg-emerald-50 text-emerald-700'
        : 'bg-slate-100 text-slate-700';
  return <span className={`rounded-xl px-2 py-2 text-center text-[11px] font-extrabold ${className}`}>{label}</span>;
}

function DetailBlock({ title, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 p-4">
      <p className="flex items-center gap-2 text-sm font-extrabold text-slate-950">
        <CheckCircle2 size={16} className="text-emerald-600" />
        {title}
      </p>
      <p className="mt-2 text-sm font-medium leading-6 text-slate-600">{value}</p>
    </div>
  );
}

export default WorkflowStepShowcase;
