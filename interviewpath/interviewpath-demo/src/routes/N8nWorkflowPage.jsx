import { useCallback, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { ArrowRight, Play, RefreshCcw } from 'lucide-react';
import ExecutionLog from '../components/n8n/ExecutionLog.jsx';
import N8nNode from '../components/n8n/N8nNode.jsx';
import NodeDetailPanel from '../components/n8n/NodeDetailPanel.jsx';
import { mockWorkflowEdges, mockWorkflowNodes, workflowLogs, workflowStatuses } from '../data/mockN8nWorkflow.js';

const edgeIds = mockWorkflowEdges.map((edge) => edge.id);

function toReactFlowNodes() {
  return mockWorkflowNodes.map((node) => ({
    id: node.id,
    type: 'n8nNode',
    position: node.position,
    data: {
      ...node,
      workflowType: node.type,
    },
  }));
}

function toReactFlowEdges(completedEdges = [], activeEdgeId = null) {
  return mockWorkflowEdges.map((edge) => {
    const completed = completedEdges.includes(edge.id);
    const active = activeEdgeId === edge.id;
    return {
      ...edge,
      type: 'smoothstep',
      animated: active,
      markerEnd: { type: MarkerType.ArrowClosed, color: completed || active ? '#2563eb' : '#94a3b8' },
      style: {
        stroke: completed ? '#16a34a' : active ? '#2563eb' : '#94a3b8',
        strokeWidth: completed || active ? 3 : 2,
      },
    };
  });
}

function formatLogTime(offsetSeconds) {
  const date = new Date(Date.now() + offsetSeconds * 1000);
  return date.toTimeString().slice(0, 8);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function N8nWorkflowPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState(toReactFlowNodes());
  const [edges, setEdges, onEdgesChange] = useEdgesState(toReactFlowEdges());
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [currentStepIndex, setCurrentStepIndex] = useState(-1);
  const [completedEdgeIds, setCompletedEdgeIds] = useState([]);
  const [isAutoRunning, setIsAutoRunning] = useState(false);
  const runTokenRef = useRef(0);

  const nodeTypes = useMemo(() => ({ n8nNode: N8nNode }), []);
  const fitViewOptions = useMemo(() => ({ padding: 0.04, maxZoom: 0.76 }), []);
  const selectedNode = useMemo(() => nodes.find((node) => node.id === selectedNodeId), [nodes, selectedNodeId]);
  const activeStepNode = useMemo(() => {
    if (currentStepIndex < 0 || currentStepIndex >= mockWorkflowNodes.length) return selectedNode;
    const activeNodeId = mockWorkflowNodes[currentStepIndex].id;
    return nodes.find((node) => node.id === activeNodeId) || selectedNode;
  }, [currentStepIndex, nodes, selectedNode]);

  const setNodeStatus = useCallback(
    (nodeId, status) => {
      setNodes((current) =>
        current.map((node) => (node.id === nodeId ? { ...node, data: { ...node.data, status } } : node)),
      );
    },
    [setNodes],
  );

  const resetWorkflow = useCallback(() => {
    runTokenRef.current += 1;
    setIsAutoRunning(false);
    setLogs([]);
    setCurrentStepIndex(-1);
    setCompletedEdgeIds([]);
    setSelectedNodeId(null);
    setNodes((current) =>
      current.map((node) => ({
        ...node,
        data: { ...node.data, status: workflowStatuses.waiting },
      })),
    );
    setEdges(toReactFlowEdges());
  }, [setEdges, setNodes]);

  const startWorkflow = useCallback(
    () => {
      setLogs([]);
      setCurrentStepIndex(0);
      setCompletedEdgeIds([]);
      setSelectedNodeId(mockWorkflowNodes[0].id);
      setNodes((current) =>
        current.map((node) => {
          const status = node.id === mockWorkflowNodes[0].id ? workflowStatuses.running : workflowStatuses.waiting;
          return { ...node, data: { ...node.data, status } };
        }),
      );
      setEdges(toReactFlowEdges());
    },
    [setEdges, setNodes],
  );

  const runWorkflow = useCallback(async () => {
    const runToken = runTokenRef.current + 1;
    runTokenRef.current = runToken;
    setIsAutoRunning(true);
    setLogs([]);
    setCurrentStepIndex(0);
    setCompletedEdgeIds([]);
    setSelectedNodeId(mockWorkflowNodes[0].id);
    setNodes((current) =>
      current.map((node) => {
        const status = node.id === mockWorkflowNodes[0].id ? workflowStatuses.running : workflowStatuses.waiting;
        return { ...node, data: { ...node.data, status } };
      }),
    );
    setEdges(toReactFlowEdges());

    const completedEdges = [];

    for (let index = 0; index < mockWorkflowNodes.length; index += 1) {
      if (runTokenRef.current !== runToken) return;
      const currentNode = mockWorkflowNodes[index];
      const incomingEdgeId = edgeIds[index - 1] || null;
      const outgoingEdgeId = edgeIds[index] || null;
      const nextNode = mockWorkflowNodes[index + 1];

      setSelectedNodeId(currentNode.id);
      setCurrentStepIndex(index);
      setEdges(toReactFlowEdges(completedEdges, incomingEdgeId));
      setNodeStatus(currentNode.id, workflowStatuses.running);
      await sleep(700);

      if (runTokenRef.current !== runToken) return;
      setNodeStatus(currentNode.id, workflowStatuses.success);
      setLogs((current) => [...current, { time: formatLogTime(index + 1), message: workflowLogs[index] }]);

      if (incomingEdgeId) completedEdges.push(incomingEdgeId);
      setCompletedEdgeIds([...completedEdges]);

      if (nextNode) {
        setNodeStatus(nextNode.id, workflowStatuses.running);
        setEdges(toReactFlowEdges(completedEdges, outgoingEdgeId));
      }

      await sleep(260);
    }

    setCurrentStepIndex(mockWorkflowNodes.length);
    setCompletedEdgeIds(edgeIds);
    setEdges(toReactFlowEdges(edgeIds));
    setIsAutoRunning(false);
  }, [setEdges, setNodeStatus, setNodes]);

  const advanceStep = useCallback(() => {
    if (currentStepIndex === -1) {
      startWorkflow();
      return;
    }

    if (currentStepIndex >= mockWorkflowNodes.length) return;

    const currentNode = mockWorkflowNodes[currentStepIndex];
    const incomingEdgeId = edgeIds[currentStepIndex - 1] || null;
    const nextNode = mockWorkflowNodes[currentStepIndex + 1];
    const outgoingEdgeId = edgeIds[currentStepIndex] || null;
    const nextCompletedEdges = incomingEdgeId
      ? Array.from(new Set([...completedEdgeIds, incomingEdgeId]))
      : completedEdgeIds;

    setNodeStatus(currentNode.id, workflowStatuses.success);
    setLogs((current) => [...current, { time: formatLogTime(currentStepIndex + 1), message: workflowLogs[currentStepIndex] }]);
    setCompletedEdgeIds(nextCompletedEdges);

    if (!nextNode) {
      setCurrentStepIndex(mockWorkflowNodes.length);
      setEdges(toReactFlowEdges(edgeIds));
      return;
    }

    setNodeStatus(nextNode.id, workflowStatuses.running);
    setSelectedNodeId(nextNode.id);
    setCurrentStepIndex(currentStepIndex + 1);
    setEdges(toReactFlowEdges(nextCompletedEdges, outgoingEdgeId));
  }, [completedEdgeIds, currentStepIndex, setEdges, setNodeStatus, startWorkflow]);

  const stepLabel =
    currentStepIndex === -1
      ? 'Ready to start'
      : currentStepIndex >= mockWorkflowNodes.length
        ? 'Workflow complete'
        : `Step ${currentStepIndex + 1} of ${mockWorkflowNodes.length}: ${mockWorkflowNodes[currentStepIndex].label}`;

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden p-5">
      <header className="mb-4 flex items-start justify-between gap-5">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-violet-600">Automation Canvas</p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-950">n8n Automation Workflow</h1>
          <p className="mt-2 max-w-3xl text-sm font-medium leading-6 text-slate-600">
            See how InterviewPath automates the full recruitment journey from CV submission to talent memory.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={runWorkflow}
            disabled={isAutoRunning}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-extrabold text-white shadow-card transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Play size={17} />
            Run Workflow
          </button>
          <button
            type="button"
            onClick={advanceStep}
            disabled={isAutoRunning || currentStepIndex >= mockWorkflowNodes.length}
            className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-extrabold text-white shadow-card transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <ArrowRight size={17} />
            Next Step
          </button>
          <button
            type="button"
            onClick={resetWorkflow}
            className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-extrabold text-slate-700 shadow-card transition hover:bg-slate-50"
          >
            <RefreshCcw size={17} />
            Reset
          </button>
        </div>
      </header>

      <section className="mb-4 rounded-3xl border border-blue-100 bg-white px-5 py-4 shadow-card">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-extrabold text-blue-950">
              n8n controls the workflow. AI creates the memory. InterviewPath turns every application into a reusable Candidate
              Passport.
            </p>
            <p className="mt-1 text-sm font-semibold leading-6 text-slate-600">
              {activeStepNode?.data?.pitchExplanation ||
                'Run Workflow auto-plays the full automation. Next Step lets you present each node manually.'}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-blue-50 px-3 py-1.5 text-xs font-extrabold text-blue-700">{stepLabel}</span>
        </div>
      </section>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_330px] gap-4">
        <div className="flex min-h-0 flex-col">
          <main className="min-h-0 flex-1 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-card">
            <ReactFlowProvider>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_, node) => setSelectedNodeId(node.id)}
                fitView
                fitViewOptions={fitViewOptions}
                minZoom={0.35}
                maxZoom={1.25}
                className="bg-slate-50"
              >
                <Background color="#cbd5e1" gap={22} size={1} />
                <MiniMap pannable zoomable nodeStrokeWidth={3} className="!rounded-2xl !border !border-slate-200 !bg-white" />
                <Controls className="!rounded-2xl !border !border-slate-200 !bg-white !shadow-card" />
              </ReactFlow>
            </ReactFlowProvider>
          </main>
          <div className="mt-4 h-[112px] shrink-0">
            <ExecutionLog logs={logs} />
          </div>
        </div>
        <NodeDetailPanel node={selectedNode} />
      </div>
    </div>
  );
}

export default N8nWorkflowPage;
