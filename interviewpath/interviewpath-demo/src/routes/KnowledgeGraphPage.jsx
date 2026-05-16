import {
  BrainCircuit,
  Crosshair,
  Database,
  FileUp,
  GitBranch,
  Plus,
  RefreshCcw,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import KnowledgeGraph from '../components/KnowledgeGraph.jsx';
import Toast from '../components/Toast.jsx';
import { buildCandidateGraph, buildCompanyGraph, candidateProfiles } from '../data/mockGraph.js';

const companyView = {
  id: 'company',
  name: 'Company RAG',
  role: 'Shared Hiring Brain',
  hubId: 'hiring-knowledge-core',
  pulseNodeIds: [
    'hiring-knowledge-core',
    'company-culture',
    'korean-work-style',
    'job-description',
    'technical-skills',
    'interview-rubric',
    'interview-questions',
    'feedback-reports',
    'leadership-expectations',
    'reporting-standard',
    'backend-team-culture-base',
    'frontend-design-standard',
    'qa-testing-standard',
    'company-tech-stack',
    'system-architecture',
    'code-review-policy',
    'sprint-rituals',
    'english-communication-standard',
    'technical-rubric',
    'culture-rubric',
    'question-bank',
    'evaluation-calibration',
    'risk-signals',
    'past-interview-outcomes',
    'hr-decision-records',
    'talent-pool-memory',
    'onboarding-playbook',
    'employee-performance-signals',
    'offer-criteria',
  ],
};

const defaultViewId = 'company';

function KnowledgeGraphPage() {
  const [selectedViewId, setSelectedViewId] = useState(defaultViewId);
  const [uploads, setUploads] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [uploadIndex, setUploadIndex] = useState(0);
  const [pulseMemory, setPulseMemory] = useState(false);
  const [centerNonce, setCenterNonce] = useState(0);
  const [toast, setToast] = useState('');

  const selectedCandidate = useMemo(
    () => candidateProfiles.find((candidate) => candidate.id === selectedViewId) || null,
    [selectedViewId],
  );

  const isCompanyView = selectedViewId === companyView.id;
  const graph = useMemo(
    () => (isCompanyView ? buildCompanyGraph(uploads) : buildCandidateGraph(selectedViewId, uploads)),
    [isCompanyView, selectedViewId, uploads],
  );
  const activeMemoryHubId = isCompanyView ? companyView.hubId : selectedCandidate?.passportId;
  const activePulseNodeIds = isCompanyView ? companyView.pulseNodeIds : selectedCandidate?.pulseNodeIds || [];

  useEffect(() => {
    const existingNode = graph.nodes.find((node) => node.id === selectedNode?.id);
    const hubNode = graph.nodes.find((node) => node.id === activeMemoryHubId);
    setSelectedNode(existingNode || hubNode || graph.nodes[0]);
  }, [activeMemoryHubId, graph, selectedNode?.id]);

  function selectView(viewId) {
    const candidate = candidateProfiles.find((item) => item.id === viewId);
    setSelectedViewId(candidate?.id || companyView.id);
    setPulseMemory(true);
    setCenterNonce((current) => current + 1);
    setToast(candidate ? `Personal memory loaded for ${candidate.name}.` : 'Company RAG graph loaded.');
    setTimeout(() => setPulseMemory(false), 2600);
    setTimeout(() => setToast(''), 2600);
  }

  function uploadKnowledge() {
    const newUpload = isCompanyView ? createCompanyUpload() : createUpload(uploadIndex, selectedCandidate);
    setUploads((current) => [...current, newUpload]);
    setSelectedNode(newUpload.node);
    setUploadIndex((current) => current + 1);
    setPulseMemory(newUpload.scope === 'candidate');
    setCenterNonce((current) => current + 1);
    setToast(isCompanyView ? 'New company knowledge node added to the shared RAG graph.' : 'New knowledge node added and linked to candidate memory.');
    setTimeout(() => setPulseMemory(false), 2600);
    setTimeout(() => setToast(''), 2600);
  }

  function centerGraph() {
    setCenterNonce((current) => current + 1);
    setToast('Force graph centered.');
    setTimeout(() => setToast(''), 1800);
  }

  function pulseMemoryHub() {
    setPulseMemory(true);
    setToast(isCompanyView ? 'Company RAG memory highlighted.' : `${selectedCandidate.name} personal memory highlighted.`);
    setTimeout(() => setPulseMemory(false), 2600);
    setTimeout(() => setToast(''), 2600);
  }

  function resetGraph() {
    setUploads([]);
    setUploadIndex(0);
    setPulseMemory(true);
    setSelectedNode(graph.nodes.find((node) => node.id === activeMemoryHubId));
    setCenterNonce((current) => current + 1);
    setToast(isCompanyView ? 'Company RAG graph reset to the shared knowledge base.' : 'Personalized RAG graph reset to the demo knowledge base.');
    setTimeout(() => setPulseMemory(false), 2400);
    setTimeout(() => setToast(''), 2400);
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden p-4">
      <Toast message={toast} />
      <header className="mb-3 flex shrink-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-violet-600">RAG Knowledge Graph</p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-950">Company Hiring Brain</h1>
          <p className="mt-1.5 max-w-3xl text-sm font-medium leading-5 text-slate-600">
            RAG is not only company knowledge. InterviewPath also builds a personal memory graph for each candidate.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <GraphStatBadge label="Memory records" value={graph.nodes.length} />
            <GraphStatBadge label="Relationships" value={graph.links.length} />
            <GraphStatBadge label={isCompanyView ? 'Company mode' : 'Personal mode'} value={isCompanyView ? 'Shared' : selectedCandidate.name.split(' ')[0]} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => selectView(companyView.id)}
              className={[
                'flex items-center gap-2 rounded-xl border px-2.5 py-1.5 text-xs font-extrabold transition',
                isCompanyView
                  ? 'border-violet-200 bg-violet-50 text-violet-800 shadow-sm'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-violet-200 hover:bg-violet-50 hover:text-violet-700',
              ].join(' ')}
            >
              <BrainCircuit size={14} />
              <span>{companyView.name}</span>
              <span className={isCompanyView ? 'text-violet-600' : 'text-slate-400'}>{companyView.role}</span>
            </button>
            {candidateProfiles.map((candidate) => {
              const active = candidate.id === selectedViewId;
              return (
                <button
                  key={candidate.id}
                  type="button"
                  onClick={() => selectView(candidate.id)}
                  className={[
                    'flex items-center gap-2 rounded-xl border px-2.5 py-1.5 text-xs font-extrabold transition',
                    active
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-800 shadow-sm'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-violet-200 hover:bg-violet-50 hover:text-violet-700',
                  ].join(' ')}
                >
                  <UserRound size={14} />
                  <span>{candidate.name}</span>
                  <span className={active ? 'text-emerald-600' : 'text-slate-400'}>{candidate.role}</span>
                </button>
              );
            })}
          </div>
        </div>
        <button
          type="button"
          onClick={uploadKnowledge}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-extrabold text-white shadow-card transition hover:bg-slate-800"
        >
          <FileUp size={18} />
          Upload Knowledge
        </button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_260px] gap-3">
        <main className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white p-2.5 shadow-card">
          <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 px-2 pt-1">
            <div>
              <p className="text-sm font-extrabold text-slate-950">{isCompanyView ? 'Live company RAG graph' : 'Live personalized graph'}</p>
              <p className="text-xs font-semibold text-slate-500">
                {isCompanyView
                  ? 'Showing the shared hiring brain: culture, job context, rubrics, outcomes, onboarding, and talent memory.'
                  : `Showing ${selectedCandidate.name} memory connected to shared company hiring knowledge.`}
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-1.5">
              <GraphControlButton icon={Crosshair} label="Center Graph" onClick={centerGraph} />
              <GraphControlButton icon={Sparkles} label="Pulse Memory" onClick={pulseMemoryHub} />
              <GraphControlButton icon={Plus} label="Add Knowledge" onClick={uploadKnowledge} />
              <GraphControlButton icon={RefreshCcw} label="Reset Graph" onClick={resetGraph} />
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-hidden rounded-2xl">
            <KnowledgeGraph
              graph={graph}
              selectedNode={selectedNode}
              onSelectNode={setSelectedNode}
              pulseMemory={pulseMemory}
              pulseNodeIds={activePulseNodeIds}
              memoryHubId={activeMemoryHubId}
              centerNonce={centerNonce}
            />
          </div>
        </main>

        <aside className="min-h-0 overflow-y-auto rounded-3xl border border-slate-200 bg-white p-4 shadow-card thin-scrollbar">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-700">
              <GitBranch size={20} />
            </div>
            <div>
              <p className="text-sm font-extrabold text-slate-950">Selected node</p>
              <p className="text-xs font-semibold text-slate-500">Drag nodes to rearrange</p>
            </div>
          </div>
          {selectedNode ? <SelectedNodeDetails node={selectedNode} /> : null}
        </aside>
      </div>
    </div>
  );
}

function SelectedNodeDetails({ node }) {
  return (
    <div className="mt-6">
      <p className="text-xs font-extrabold uppercase tracking-[0.18em] text-slate-400">{node.category}</p>
      <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">{node.label}</h2>
      <p className="mt-3 text-sm font-medium leading-6 text-slate-600">{node.description || node.detail}</p>

      {node.kind === 'candidate-passport' ? <CandidatePassportDetails node={node} /> : null}
      {node.kind === 'personal-learning' ? <PersonalLearningDetails node={node} /> : null}

      {node.kind !== 'candidate-passport' ? (
        <div className="mt-5 rounded-2xl bg-slate-950 p-4 text-white">
          <p className="flex items-center gap-2 text-sm font-extrabold">
            <Database size={17} />
            Memory role
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-300">{node.memoryRole}</p>
        </div>
      ) : null}

      {node.kind !== 'personal-learning' ? (
        <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-4">
          <p className="text-sm font-extrabold text-blue-900">How RAG uses this node</p>
          <p className="mt-2 text-sm font-semibold leading-6 text-blue-800">{node.ragUse}</p>
        </div>
      ) : null}

      {node.relatedEvidence?.length ? (
        <div className="mt-4 rounded-2xl border border-violet-100 bg-violet-50 p-4">
          <p className="text-sm font-extrabold text-violet-900">Related evidence</p>
          <EvidenceTags items={node.relatedEvidence} />
        </div>
      ) : null}

      <div className="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
        <p className="text-sm font-extrabold text-emerald-900">Demo cue</p>
        <p className="mt-2 text-sm font-semibold leading-6 text-emerald-800">{node.demoCue}</p>
      </div>
    </div>
  );
}

function CandidatePassportDetails({ node }) {
  return (
    <>
      <div className="mt-5 rounded-2xl bg-slate-950 p-4 text-white">
        <p className="flex items-center gap-2 text-sm font-extrabold">
          <Database size={17} />
          Current readiness
        </p>
        <div className="mt-3 grid grid-cols-1 gap-2">
          {(node.readiness || []).map((item) => (
            <div key={item.label} className="flex items-center justify-between rounded-xl bg-white/8 px-3 py-2">
              <span className="text-xs font-bold text-slate-300">{item.label}</span>
              <span className="text-sm font-extrabold text-emerald-300">{item.value}</span>
            </div>
          ))}
        </div>
      </div>
      <DetailList title="What this candidate understands" items={node.understands} tone="blue" />
      <DetailList title="Needs improvement" items={node.needsImprovement} tone="amber" />
      <DetailList title="Related company knowledge" items={node.relatedCompanyKnowledge} tone="violet" />
      <div className="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
        <p className="text-sm font-extrabold text-emerald-900">Recommended next action</p>
        <p className="mt-2 text-sm font-semibold leading-6 text-emerald-800">{node.recommendedNextAction}</p>
      </div>
    </>
  );
}

function PersonalLearningDetails({ node }) {
  return (
    <>
      <DetailList title="Learning evidence" items={node.learningEvidence} tone="orange" />
      <DetailList title="Connected company knowledge" items={node.connectedCompanyKnowledge} tone="blue" />
      <div className="mt-4 rounded-2xl border border-amber-100 bg-amber-50 p-4">
        <p className="text-sm font-extrabold text-amber-900">Improvement level</p>
        <p className="mt-2 text-sm font-semibold leading-6 text-amber-800">{node.improvementLevel}</p>
      </div>
      <div className="mt-4 rounded-2xl border border-fuchsia-100 bg-fuchsia-50 p-4">
        <p className="text-sm font-extrabold text-fuchsia-900">AI coaching note</p>
        <p className="mt-2 text-sm font-semibold leading-6 text-fuchsia-800">{node.coachingNote}</p>
      </div>
    </>
  );
}

function DetailList({ title, items = [], tone }) {
  if (!items.length) return null;

  const toneClasses = {
    blue: 'border-blue-100 bg-blue-50 text-blue-900 marker:text-blue-500',
    amber: 'border-amber-100 bg-amber-50 text-amber-900 marker:text-amber-500',
    violet: 'border-violet-100 bg-violet-50 text-violet-900 marker:text-violet-500',
    orange: 'border-orange-100 bg-orange-50 text-orange-900 marker:text-orange-500',
  };

  return (
    <div className={`mt-4 rounded-2xl border p-4 ${toneClasses[tone] || toneClasses.blue}`}>
      <p className="text-sm font-extrabold">{title}</p>
      <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm font-semibold leading-6">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function EvidenceTags({ items }) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className="rounded-full border border-violet-100 bg-white px-2.5 py-1 text-[11px] font-extrabold text-violet-700">
          {item}
        </span>
      ))}
    </div>
  );
}

function createUpload(uploadIndex, candidate) {
  const mode = uploadIndex % 3;
  const timestamp = Date.now();

  if (mode === 0) {
    return createCompanyUpload(timestamp);
  }

  if (mode === 1) {
    const shortName = candidate.name.split(' ')[0];
    const nodeId = `${candidate.id}-deadline-story-${timestamp}`;
    return {
      scope: 'candidate',
      candidateId: candidate.id,
      node: {
        id: nodeId,
        label: `${shortName} Deadline Story`,
        category: 'Feedback History',
        group: 'feedback',
        color: '#facc15',
        size: 9,
        x: 255,
        y: 315,
        isNew: true,
        candidateId: candidate.id,
        description: `A newly captured practice story about how ${candidate.name} handles deadline pressure.`,
        memoryRole: 'Adds one concrete behavioral example to the personal candidate memory graph.',
        ragUse: 'Retrieves this story when HR asks culture-fit questions about teamwork under deadline pressure.',
        relatedEvidence: ['Deadline pressure', 'Teamwork example', 'Culture-fit story'],
        demoCue: 'Use this uploaded node to show the Candidate Passport growing after practice.',
      },
      links: [
        { source: candidate.passportId, target: nodeId, label: 'remembers', strength: 0.52, distance: 122, active: true },
        { source: candidate.learnedNodeId, target: nodeId, label: 'supports', strength: 0.42, distance: 130, active: true },
      ],
    };
  }

  const nodeId = `${candidate.id}-star-practice-result-${timestamp}`;
  return {
    scope: 'candidate',
    candidateId: candidate.id,
    node: {
      id: nodeId,
      label: 'English STAR Practice Result',
      category: 'Personal Learning',
      group: 'learning',
      color: '#fb7185',
      size: 9,
      x: -20,
      y: 330,
      isNew: true,
      candidateId: candidate.id,
      kind: 'personal-learning',
      description: `A new AI practice result showing how ${candidate.name} improved answer structure using STAR.`,
      memoryRole: 'Stores a coaching result that connects English answer patterns with practice history.',
      ragUse: 'Retrieves this practice result before giving the next English clarity recommendation.',
      learningEvidence: ['Situation stated earlier', 'Action is more specific', 'Result still needs a metric'],
      connectedCompanyKnowledge: ['Interview Rubric', 'Feedback Reports'],
      improvementLevel: 'Improving, still needs stronger result detail.',
      coachingNote: 'Keep the answer short, name the action clearly, and finish with a measurable result.',
      relatedEvidence: ['STAR method', 'English clarity', 'Practice feedback'],
      demoCue: 'Use this uploaded node to show personal memory evolving after each coaching session.',
    },
    links: [
      { source: candidate.englishNodeId, target: nodeId, label: 'improves', strength: 0.52, distance: 122, active: true },
      { source: candidate.practiceNodeId, target: nodeId, label: 'stores', strength: 0.45, distance: 130, active: true },
    ],
  };
}

function createCompanyUpload(timestamp = Date.now()) {
  const nodeId = `backend-team-culture-${timestamp}`;
  return {
    scope: 'company',
    node: {
      id: nodeId,
      label: 'Backend Team Culture',
      category: 'Company Memory',
      group: 'company',
      color: '#9333ea',
      size: 9,
      x: -330,
      y: -90,
      isNew: true,
      description: 'Team norms for code review, ownership, sprint communication, and release support.',
      memoryRole: 'Adds team-specific expectations to the shared company memory layer.',
      ragUse: 'Retrieves backend team norms before evaluating collaboration and ownership answers.',
      relatedEvidence: ['Code review habits', 'Sprint communication', 'Release support'],
      demoCue: 'Use this uploaded node to show how company knowledge expands without rebuilding the system.',
    },
    links: [{ source: 'company-culture', target: nodeId, label: 'expands', strength: 0.46, distance: 130, active: true }],
  };
}

function GraphControlButton({ icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-2 text-[11px] font-extrabold text-slate-700 shadow-sm transition hover:border-violet-200 hover:bg-violet-50 hover:text-violet-700"
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

function GraphStatBadge({ label, value }) {
  return (
    <div className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-extrabold text-slate-700 shadow-sm">
      <span className="text-slate-400">{label}</span>
      <span className="ml-2 text-slate-950">{value}</span>
    </div>
  );
}

export default KnowledgeGraphPage;
