import { Pencil, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api.js';
import { buildTree } from '../lib/tree.js';

const inputClass =
  'rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none focus:border-blue-500';
const primaryButton =
  'rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-card transition hover:bg-blue-700 disabled:opacity-60';

function flatten(nodes, depth = 0) {
  return nodes.flatMap((node) => [{ id: node.id, name: node.name, depth }, ...flatten(node.children, depth + 1)]);
}

function DepartmentNode({ node, canEdit, onRename, onDelete, t }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(node.name);

  const save = async (event) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (trimmed && trimmed !== node.name) await onRename(node, trimmed);
    setEditing(false);
  };

  return (
    <li role="treeitem" aria-expanded={node.children.length > 0 ? true : undefined} aria-selected={false}>
      <div className="flex items-center gap-2 py-1">
        {editing ? (
          <form onSubmit={save} className="flex items-center gap-2">
            <input
              aria-label={`${t('common.rename')} ${node.name}`}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputClass}
            />
            <button type="submit" className={primaryButton}>
              {t('common.save')}
            </button>
            <button
              type="button"
              onClick={() => {
                setName(node.name);
                setEditing(false);
              }}
              className="text-sm font-semibold text-slate-500 hover:text-slate-950"
            >
              {t('common.cancel')}
            </button>
          </form>
        ) : (
          <>
            <span className="text-sm font-semibold text-slate-900">{node.name}</span>
            {canEdit && (
              <>
                <button
                  type="button"
                  title={t('common.rename')}
                  aria-label={`${t('common.rename')} ${node.name}`}
                  onClick={() => setEditing(true)}
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-950"
                >
                  <Pencil size={14} />
                </button>
                <button
                  type="button"
                  title={t('departments.delete')}
                  aria-label={`${t('departments.delete')} ${node.name}`}
                  onClick={() => onDelete(node)}
                  className="rounded-lg p-1 text-slate-400 hover:bg-red-50 hover:text-red-700"
                >
                  <Trash2 size={14} />
                </button>
              </>
            )}
          </>
        )}
      </div>
      {node.children.length > 0 && (
        <ul role="group" className="ml-5 border-l border-slate-200 pl-3">
          {node.children.map((child) => (
            <DepartmentNode key={child.id} node={child} canEdit={canEdit} onRename={onRename} onDelete={onDelete} t={t} />
          ))}
        </ul>
      )}
    </li>
  );
}

function DepartmentTree({ companyId, departments, canEdit, onChanged }) {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [parentId, setParentId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const tree = useMemo(() => buildTree(departments), [departments]);
  const options = useMemo(() => flatten(tree), [tree]);

  const changed = () => onChanged();

  const add = async (event) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setError('');
    setBusy(true);
    try {
      await api(`/api/companies/${companyId}/departments`, {
        method: 'POST',
        body: { name: trimmed, parent_id: parentId === '' ? null : Number(parentId) },
      });
      setName('');
      setParentId('');
      await changed();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const rename = async (node, newName) => {
    setError('');
    try {
      await api(`/api/companies/${companyId}/departments/${node.id}`, { method: 'PATCH', body: { name: newName } });
      await changed();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (node) => {
    if (!window.confirm(t('departments.confirmDelete'))) return;
    setError('');
    try {
      await api(`/api/companies/${companyId}/departments/${node.id}`, { method: 'DELETE' });
      await changed();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <h2 className="text-lg font-extrabold tracking-tight">{t('departments.title')}</h2>

      {error && (
        <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-800">
          {error}
        </p>
      )}

      {tree.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">{t('departments.empty')}</p>
      ) : (
        <ul role="tree" className="mt-4">
          {tree.map((node) => (
            <DepartmentNode key={node.id} node={node} canEdit={canEdit} onRename={rename} onDelete={remove} t={t} />
          ))}
        </ul>
      )}

      {canEdit && (
        <form onSubmit={add} className="mt-5 flex flex-wrap items-end gap-3">
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('departments.newName')}</span>
            <input value={name} onChange={(e) => setName(e.target.value)} className={`${inputClass} mt-1`} />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('departments.parent')}</span>
            <select value={parentId} onChange={(e) => setParentId(e.target.value)} className={`${inputClass} mt-1`}>
              <option value="">{t('departments.noParent')}</option>
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {'  '.repeat(option.depth)}
                  {option.name}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={busy} className={primaryButton}>
            {t('departments.add')}
          </button>
        </form>
      )}
    </section>
  );
}

export default DepartmentTree;
