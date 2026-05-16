import { Braces, CheckCircle2, Info } from 'lucide-react';

function NodeDetailPanel({ node, compact = false }) {
  if (compact && !node) {
    return (
      <aside className="flex h-full items-center justify-center rounded-2xl border border-slate-200 bg-white p-4 text-center shadow-card">
        <div>
          <Info size={22} className="mx-auto text-slate-400" />
          <p className="mt-2 text-sm font-extrabold text-slate-700">Select a workflow node</p>
          <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">Node details appear here.</p>
        </div>
      </aside>
    );
  }

  if (compact && node) {
    const data = node.data;

    return (
      <aside className="h-full overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-card">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-extrabold uppercase tracking-[0.18em] text-blue-600">Selected Node</p>
            <h2 className="mt-1 truncate text-lg font-extrabold tracking-tight text-slate-950">{data.label}</h2>
          </div>
          <span className="shrink-0 rounded-full bg-blue-50 px-3 py-1 text-xs font-extrabold text-blue-700">{data.status}</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="rounded-full bg-slate-950 px-2.5 py-1 text-[10px] font-extrabold text-white">{data.workflowType}</span>
        </div>
        <p className="mt-2 line-clamp-2 text-xs font-semibold leading-5 text-slate-600">{data.description}</p>
      </aside>
    );
  }

  if (!node) {
    return (
      <aside className="flex h-full flex-col rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
        <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
          <Info size={32} className="text-slate-400" />
          <p className="mt-3 text-sm font-extrabold text-slate-700">Select a workflow node</p>
          <p className="mt-2 text-sm font-medium leading-6 text-slate-500">
            Click any n8n node to inspect inputs, processing logic, output, and example JSON payload.
          </p>
        </div>
      </aside>
    );
  }

  const data = node.data;

  return (
    <aside className="thin-scrollbar h-full overflow-y-auto rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.18em] text-blue-600">Selected Node</p>
          <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">{data.label}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full bg-slate-950 px-3 py-1 text-xs font-extrabold text-white">{data.workflowType}</span>
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-extrabold text-blue-700">{data.status}</span>
          </div>
        </div>
      </div>

      <p className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm font-semibold leading-6 text-slate-600">{data.description}</p>

      <div className="mt-5 space-y-3">
        <DetailBlock title="Input data" value={data.input} />
        <DetailBlock title="Processing logic" value={data.process} />
        <DetailBlock title="Output data" value={data.output} />
      </div>

      <div className="mt-5 rounded-2xl bg-slate-950 p-4 text-white">
        <p className="flex items-center gap-2 text-sm font-extrabold">
          <Braces size={17} />
          Example JSON payload
        </p>
        <pre className="thin-scrollbar mt-3 max-h-[240px] overflow-auto rounded-xl bg-slate-900 p-3 text-xs leading-5 text-emerald-100">
          {JSON.stringify(data.jsonPayload, null, 2)}
        </pre>
      </div>
    </aside>
  );
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

export default NodeDetailPanel;
