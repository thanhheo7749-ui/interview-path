import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';
import { EmptyState, ErrorAlert, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import {
  AUDIT_ACTIONS,
  getRetention,
  listApplicationChoices,
  listAudit,
  listConsents,
  runFairnessCheck,
} from '../lib/trust.js';

const TABS = ['consents', 'audit', 'retention', 'fairness'];
const formatDate = (value) => (value ? new Date(value).toLocaleString() : '');

// Loads one resource for the active tab and reloads when `deps` change.
function useLoad(load, deps) {
  const key = JSON.stringify(deps);
  const [state, setState] = useState({ key: null, data: null, error: '' });
  useEffect(() => {
    let cancelled = false;
    load()
      .then((data) => {
        if (!cancelled) setState({ key, data, error: '' });
      })
      .catch((err) => {
        if (!cancelled) setState({ key, data: null, error: err.message });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  // A result for older inputs is not shown while the new one loads.
  return state.key === key ? state : { data: null, error: '' };
}

function Pager({ page, pageSize, total, onPage }) {
  const { t } = useTranslation();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center gap-3 text-sm text-slate-600">
      <button type="button" className={secondaryButton} disabled={page <= 1} onClick={() => onPage(page - 1)}>
        {t('trust.previous')}
      </button>
      <span>{t('trust.pageOf', { page, pages })}</span>
      <button type="button" className={secondaryButton} disabled={page >= pages} onClick={() => onPage(page + 1)}>
        {t('trust.next')}
      </button>
    </div>
  );
}

const th = 'px-4 py-3 text-left text-xs font-bold uppercase tracking-[0.12em] text-slate-500';
const td = 'px-4 py-3 align-top text-sm text-slate-800';

function ConsentsTab({ companyId }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const { data, error } = useLoad(() => listConsents(companyId, page), [companyId, page]);
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t('trust.consents.intro')}</p>
      <ErrorAlert message={error} />
      {data && data.items.length === 0 && <EmptyState>{t('trust.consents.empty')}</EmptyState>}
      {data && data.items.length > 0 && (
        <>
          <div className={`${cardClass} overflow-x-auto p-0`}>
            <table className="w-full">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className={th}>{t('trust.consents.alias')}</th>
                  <th className={th}>{t('trust.consents.purpose')}</th>
                  <th className={th}>{t('trust.consents.version')}</th>
                  <th className={th}>{t('trust.consents.granted')}</th>
                  <th className={th}>{t('trust.consents.status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td className={`${td} font-bold`}>{row.alias ?? t('trust.consents.noAlias')}</td>
                    <td className={td}>{t(`trust.purposes.${row.purpose}`, { defaultValue: row.purpose })}</td>
                    <td className={td}>{row.version}</td>
                    <td className={td}>{formatDate(row.granted_at)}</td>
                    <td className={td}>
                      {row.withdrawn_at
                        ? t('trust.consents.withdrawn', { date: formatDate(row.withdrawn_at) })
                        : t('trust.consents.active')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}

function payloadText(payload) {
  const entries = Object.entries(payload ?? {});
  return entries.map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`).join(', ');
}

function AuditTab({ companyId }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [action, setAction] = useState('');
  const { data, error } = useLoad(() => listAudit(companyId, { action, page }), [companyId, action, page]);
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t('trust.audit.intro')}</p>
      <label className="flex items-center gap-3 text-sm font-semibold text-slate-700">
        {t('trust.audit.filter')}
        <select
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
          className={inputClass}
        >
          <option value="">{t('trust.audit.allActions')}</option>
          {AUDIT_ACTIONS.map((name) => (
            <option key={name} value={name}>
              {t(`trust.actions.${name}`, { defaultValue: name })}
            </option>
          ))}
        </select>
      </label>
      <ErrorAlert message={error} />
      {data && data.items.length === 0 && <EmptyState>{t('trust.audit.empty')}</EmptyState>}
      {data && data.items.length > 0 && (
        <>
          <div className={`${cardClass} overflow-x-auto p-0`}>
            <table className="w-full">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className={th}>{t('trust.audit.when')}</th>
                  <th className={th}>{t('trust.audit.action')}</th>
                  <th className={th}>{t('trust.audit.actor')}</th>
                  <th className={th}>{t('trust.audit.target')}</th>
                  <th className={th}>{t('trust.audit.ai')}</th>
                  <th className={th}>{t('trust.audit.details')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td className={td}>{formatDate(row.created_at)}</td>
                    <td className={`${td} font-bold`}>{t(`trust.actions.${row.action}`, { defaultValue: row.action })}</td>
                    <td className={td}>
                      {row.actor_user_id != null ? t('trust.audit.staff', { id: row.actor_user_id }) : t('trust.audit.system')}
                    </td>
                    <td className={td}>
                      {row.target_type}
                      {row.target_id != null ? ` #${row.target_id}` : ''}
                    </td>
                    <td className={td}>{[row.ai_provider, row.ai_model, row.prompt_version].filter(Boolean).join(' / ')}</td>
                    <td className={`${td} break-words text-slate-600`}>{payloadText(row.payload)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className={cardClass}>
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-extrabold tracking-tight text-slate-950">{value}</p>
      {hint && <p className="mt-2 text-sm text-slate-600">{hint}</p>}
    </div>
  );
}

function RetentionTab({ companyId }) {
  const { t } = useTranslation();
  const { data, error } = useLoad(() => getRetention(companyId), [companyId]);
  return (
    <div className="space-y-4">
      <ErrorAlert message={error} />
      {data && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Stat
              label={t('trust.retention.period')}
              value={t('trust.retention.days', { count: data.retention_days })}
              hint={t('trust.retention.periodHint', { undecided: data.undecided_retention_days })}
            />
            <Stat label={t('trust.retention.awaiting')} value={data.awaiting_deletion} hint={t('trust.retention.awaitingHint')} />
            <Stat label={t('trust.retention.dueNow')} value={data.due_now} hint={t('trust.retention.dueNowHint')} />
            <Stat label={t('trust.retention.anonymized')} value={data.anonymized} hint={t('trust.retention.anonymizedHint')} />
          </div>
          <section className={`${cardClass} space-y-2 text-sm text-slate-700`}>
            <p>
              <span className="font-bold text-slate-950">{t('trust.retention.deletedLabel')}</span> {t('trust.retention.deleted')}
            </p>
            <p>
              <span className="font-bold text-slate-950">{t('trust.retention.keptLabel')}</span> {t('trust.retention.kept')}
            </p>
          </section>
        </>
      )}
    </div>
  );
}

function resultSentence(t, result) {
  if (result.identical_blind_text && result.identical_result) return t('trust.fairness.resultSame');
  if (result.identical_blind_text) return t('trust.fairness.resultTextSameOnly');
  if (result.identical_result) return t('trust.fairness.resultTextDiffers');
  return t('trust.fairness.resultDiffers');
}

function FairnessTab({ companyId }) {
  const { t } = useTranslation();
  const { data: choices, error: loadError } = useLoad(() => listApplicationChoices(companyId), [companyId]);
  const [applicationId, setApplicationId] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const run = async () => {
    setRunning(true);
    setError('');
    setResult(null);
    try {
      setResult(await runFairnessCheck(companyId, Number(applicationId)));
    } catch (err) {
      setError(err.status === 409 ? t('trust.fairness.unavailable', { reason: err.message }) : err.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t('trust.fairness.intro')}</p>
      <ErrorAlert message={loadError} />
      {choices && choices.length === 0 && <EmptyState>{t('trust.fairness.noApplications')}</EmptyState>}
      {choices && choices.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-semibold text-slate-700">
            {t('trust.fairness.application')}
            <select value={applicationId} onChange={(e) => setApplicationId(e.target.value)} className={inputClass}>
              <option value="">{t('trust.fairness.choose')}</option>
              {choices.map((choice) => (
                <option key={choice.id} value={choice.id}>
                  {choice.alias} - {choice.jobTitle}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className={primaryButton} disabled={!applicationId || running} onClick={run}>
            {running ? t('trust.fairness.running') : t('trust.fairness.run')}
          </button>
        </div>
      )}
      <ErrorAlert message={error} />
      {result && (
        <section className="space-y-4">
          <p data-testid="fairness-result" className={`${cardClass} text-sm font-bold text-slate-950`}>
            {resultSentence(t, result)}
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className={cardClass}>
              <h3 className="text-sm font-extrabold text-slate-950">{t('trust.fairness.original')}</h3>
              <pre data-testid="fairness-original" className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-700">
                {result.original_blind_text}
              </pre>
            </div>
            <div className={cardClass}>
              <h3 className="text-sm font-extrabold text-slate-950">{t('trust.fairness.swapped')}</h3>
              <pre data-testid="fairness-swapped" className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-700">
                {result.swapped_blind_text}
              </pre>
            </div>
          </div>
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {t('trust.fairness.limit')}
          </p>
        </section>
      )}
    </div>
  );
}

function TrustPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [tab, setTab] = useState('consents');

  if (companyId == null) return null;
  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('trust.title')}</h1>
      <p className="text-sm text-slate-600">{t('trust.intro')}</p>
      <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">{t('trust.legalNote')}</p>
      <div role="tablist" className="flex gap-2 border-b border-slate-200">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={[
              '-mb-px rounded-t-xl border border-b-0 px-4 py-2 text-sm font-bold transition',
              tab === name ? 'border-slate-200 bg-white text-slate-950' : 'border-transparent text-slate-500 hover:text-slate-950',
            ].join(' ')}
          >
            {t(`trust.tabs.${name}`)}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === 'consents' && <ConsentsTab companyId={companyId} />}
        {tab === 'audit' && <AuditTab companyId={companyId} />}
        {tab === 'retention' && <RetentionTab companyId={companyId} />}
        {tab === 'fairness' && <FairnessTab companyId={companyId} />}
      </div>
    </div>
  );
}

export default TrustPage;
