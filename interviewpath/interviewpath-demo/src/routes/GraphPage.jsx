import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import KnowledgeGraph from '../components/KnowledgeGraph.jsx';
import { api } from '../lib/api.js';
import { getGraph } from '../lib/kb.js';
import { LAYERS, LAYER_COLORS } from '../lib/layers.js';

const AUDIENCES = ['hr', 'manager', 'employee', 'candidate'];
const EMPTY_GRAPH = { nodes: [], links: [] };

function GraphPage() {
  const { membership } = useCompany();
  if (membership && membership.role !== 'hr') return <Navigate to="/settings" replace />;
  if (!membership) return null;
  // Keyed by company so nothing from the previous company survives a switch.
  return <GraphExplorer key={membership.company_id} companyId={membership.company_id} />;
}

function GraphExplorer({ companyId }) {
  const { t } = useTranslation();
  const [viewAs, setViewAs] = useState('hr');
  const [departmentId, setDepartmentId] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [result, setResult] = useState({ key: null, graph: EMPTY_GRAPH, failed: false });
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api(`/api/companies/${companyId}/departments`)
      .then((data) => {
        if (!cancelled) setDepartments(data);
      })
      .catch(() => {
        if (!cancelled) setDepartments([]);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const requestKey = `${viewAs}:${viewAs === 'manager' ? departmentId : ''}`;
  useEffect(() => {
    let cancelled = false;
    getGraph(companyId, { viewAs, departmentId: viewAs === 'manager' ? departmentId : null })
      .then((graph) => {
        if (!cancelled) setResult({ key: requestKey, graph, failed: false });
      })
      .catch(() => {
        if (!cancelled) setResult({ key: requestKey, graph: EMPTY_GRAPH, failed: true });
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, viewAs, departmentId, requestKey]);

  const loading = result.key !== requestKey;
  const graph = useMemo(() => {
    const ids = new Set(result.graph.nodes.map((node) => node.id));
    // Only guards the canvas against a dangling link; which nodes appear is decided by the server.
    return { nodes: result.graph.nodes, links: result.graph.links.filter((l) => ids.has(l.source) && ids.has(l.target)) };
  }, [result.graph]);
  const nodesById = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph]);
  const selected = nodesById.get(selectedId) ?? null;
  const connections = useMemo(
    () =>
      selected
        ? graph.links
            .filter((l) => l.source === selected.id || l.target === selected.id)
            .map((l) => ({
              relation: l.relation,
              outgoing: l.source === selected.id,
              other: nodesById.get(l.source === selected.id ? l.target : l.source),
            }))
        : [],
    [graph.links, nodesById, selected],
  );

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">{t('graph.title')}</h1>
        <p className="mt-1 text-sm text-slate-500">{t('graph.subtitle')}</p>
      </div>

      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">{t('graph.viewAs')}</span>
          <div role="group" aria-label={t('graph.viewAs')} className="flex flex-wrap gap-2">
            {AUDIENCES.map((audience) => (
              <button
                key={audience}
                type="button"
                aria-pressed={viewAs === audience}
                onClick={() => setViewAs(audience)}
                className={[
                  'rounded-xl px-3 py-2 text-sm font-semibold transition',
                  viewAs === audience ? 'bg-slate-950 text-white shadow-card' : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
                ].join(' ')}
              >
                {t(`graph.audiences.${audience}`)}
              </button>
            ))}
          </div>
          {viewAs === 'manager' && (
            <select
              aria-label={t('graph.department')}
              value={departmentId ?? ''}
              onChange={(e) => setDepartmentId(e.target.value === '' ? null : Number(e.target.value))}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-950"
            >
              <option value="">{t('graph.anyDepartment')}</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          )}
        </div>
        <p className="text-xs font-semibold text-slate-500">{t('graph.simulateNote')}</p>
      </section>

      <div className="flex flex-wrap items-center gap-6 text-sm font-semibold text-slate-700">
        <span>
          {t('graph.nodeCount')}: <strong data-testid="graph-node-count">{loading ? '' : graph.nodes.length}</strong>
        </span>
        <span>
          {t('graph.linkCount')}: <strong data-testid="graph-link-count">{loading ? '' : graph.links.length}</strong>
        </span>
        <ul aria-label={t('graph.legend')} className="flex flex-wrap items-center gap-4">
          {LAYERS.map((layer) => (
            <li key={layer} className="flex items-center gap-2">
              <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: LAYER_COLORS[layer] }} />
              {t(`graph.layers.${layer}`)}
            </li>
          ))}
        </ul>
      </div>

      {result.failed && !loading && (
        <p role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-800">
          {t('graph.loadFailed')}
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="h-[560px] rounded-2xl border border-slate-200 bg-white shadow-card">
          {graph.nodes.length > 0 ? (
            <KnowledgeGraph
              graph={graph}
              selectedNode={selected}
              onSelectNode={(node) => setSelectedId(node.id)}
            />
          ) : (
            !loading &&
            !result.failed && <p className="p-6 text-sm font-semibold text-slate-500">{t('graph.empty')}</p>
          )}
        </div>

        <aside aria-label={t('graph.detail')} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
          <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">{t('graph.detail')}</h2>
          {selected ? (
            <div data-testid="graph-detail" className="space-y-2 text-sm">
              <p className="text-lg font-extrabold text-slate-950">{selected.title}</p>
              <p>
                <span className="font-bold text-slate-500">{t('graph.type')}: </span>
                {t(`graph.types.${selected.type}`, { defaultValue: selected.type })}
              </p>
              <p className="flex items-center gap-2">
                <span className="font-bold text-slate-500">{t('graph.layer')}: </span>
                <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: LAYER_COLORS[selected.layer] }} />
                {t(`graph.layers.${selected.layer}`, { defaultValue: selected.layer })}
              </p>
              <p className="text-xs text-slate-500">{t('graph.bodyUnavailable')}</p>
              <p className="font-bold text-slate-500">{t('graph.connections')}</p>
              {connections.length === 0 ? (
                <p className="text-slate-500">{t('graph.noConnections')}</p>
              ) : (
                <ul className="space-y-1">
                  {connections.map((c, index) => (
                    <li key={`${c.relation}-${c.other?.id}-${index}`} className="text-slate-700">
                      {c.outgoing ? `${c.relation} → ` : `← ${c.relation} `}
                      <span className="font-semibold">{c.other?.title}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">{t('graph.noSelection')}</p>
          )}
        </aside>
      </div>

      {graph.nodes.length > 0 && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
          <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">{t('graph.nodeList')}</h2>
          <ul data-testid="graph-node-list" className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {graph.nodes.map((node) => (
              <li key={node.id}>
                <button
                  type="button"
                  aria-pressed={selectedId === node.id}
                  onClick={() => setSelectedId(node.id)}
                  className={[
                    'flex w-full items-center gap-2 rounded-xl border px-3 py-2 text-left text-sm font-semibold transition',
                    selectedId === node.id ? 'border-slate-950 bg-slate-50' : 'border-slate-200 hover:bg-slate-50',
                  ].join(' ')}
                >
                  <span aria-hidden="true" className="inline-block h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: LAYER_COLORS[node.layer] }} />
                  <span className="min-w-0 flex-1 truncate">{node.title}</span>
                  <span className="shrink-0 text-xs font-bold uppercase text-slate-400">{t(`graph.layers.${node.layer}`, { defaultValue: node.layer })}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default GraphPage;
