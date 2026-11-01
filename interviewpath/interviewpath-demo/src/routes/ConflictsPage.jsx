import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';
import { EmptyState, ErrorAlert, WarningList, cardClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import { listConflicts, notifyKbChanged, resolveConflict } from '../lib/kb.js';

function Side({ label, node }) {
  const { t } = useTranslation();
  if (!node) return <div className="rounded-xl border border-slate-200 bg-slate-50 p-4" />;
  // Sources are optional: the conflicts route may not return quotes.
  const sources = Array.isArray(node.sources) ? node.sources : [];
  return (
    <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid={`conflict-${label}`}>
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">{t('conflicts.source', { label })}</p>
      <p className="font-extrabold text-slate-950">{node.title}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="font-semibold text-slate-500">{t('conflicts.value')}</dt>
        <dd className="font-bold text-slate-900">{node.fact_value}</dd>
        <dt className="font-semibold text-slate-500">{t('conflicts.unit')}</dt>
        <dd className="text-slate-900">{node.fact_unit || t('common.none')}</dd>
        <dt className="font-semibold text-slate-500">{t('conflicts.scope')}</dt>
        <dd className="text-slate-900">{node.scope_text || t('common.none')}</dd>
        <dt className="font-semibold text-slate-500">{t('conflicts.layer')}</dt>
        <dd className="text-slate-900">{t(`layers.${node.visibility}`, { defaultValue: node.visibility })}</dd>
      </dl>
      {sources.map((source) => (
        <blockquote key={`${source.document_title}-${source.quote}`} className="border-l-4 border-blue-300 pl-3 text-sm text-slate-700">
          <p>{source.quote}</p>
          <footer className="mt-1 text-xs text-slate-500">{source.document_title}</footer>
        </blockquote>
      ))}
    </div>
  );
}

function ConflictsPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [conflicts, setConflicts] = useState(null);
  const [error, setError] = useState('');
  const [warnings, setWarnings] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    listConflicts(companyId)
      .then((data) => {
        if (!cancelled) setConflicts(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const resolve = async (conflict, action) => {
    setError('');
    setBusy(true);
    try {
      const result = await resolveConflict(companyId, conflict.id, action);
      setWarnings(result?.warnings ?? []);
      setConflicts((current) => current.filter((c) => c.id !== conflict.id));
      notifyKbChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('conflicts.title')}</h1>
      <p className="text-sm text-slate-600">{t('conflicts.intro')}</p>
      <ErrorAlert message={error} />
      <WarningList warnings={warnings} onDismiss={() => setWarnings([])} />

      {conflicts && conflicts.length === 0 && <EmptyState>{t('conflicts.empty')}</EmptyState>}

      {(conflicts ?? []).map((conflict) => (
        <section key={conflict.id} className={`${cardClass} space-y-4`}>
          <div className="grid gap-4 md:grid-cols-2">
            <Side label="A" node={conflict.node_a} />
            <Side label="B" node={conflict.node_b} />
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" disabled={busy} onClick={() => resolve(conflict, 'a')} className={primaryButton}>
              {t('conflicts.keepA')}
            </button>
            <button type="button" disabled={busy} onClick={() => resolve(conflict, 'b')} className={primaryButton}>
              {t('conflicts.keepB')}
            </button>
            <button type="button" disabled={busy} onClick={() => resolve(conflict, 'different_scope')} className={secondaryButton}>
              {t('conflicts.differentScope')}
            </button>
          </div>
        </section>
      ))}
    </div>
  );
}

export default ConflictsPage;
