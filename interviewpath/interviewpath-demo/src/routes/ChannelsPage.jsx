import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import { ErrorAlert, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import { DataToggle, SimulatedBanner } from '../components/SimulatedBanner.jsx';
import { errorText, getChannels, getCommentary, percent, saveCost, sortRows, uploadCostsCsv, vnd } from '../lib/insights.js';

// `format` turns a row into the text shown; `key` is what the column sorts on.
const COLUMNS = [
  { key: 'channel' },
  { key: 'applications' },
  { key: 'cv_meets' },
  { key: 'sessions_completed' },
  { key: 'completion_rate', format: (row) => percent(row.completion_rate) },
  { key: 'hr_approved' },
  { key: 'approval_rate', format: (row) => percent(row.approval_rate) },
  { key: 'hidden_gems' },
  { key: 'interviews' },
  { key: 'hires' },
  { key: 'cost', format: (row, t) => (row.cost == null ? t('insights.notEntered') : vnd(row.cost)) },
  { key: 'cost_per_approved', format: (row) => vnd(row.cost_per_approved) },
];

const thisMonth = () => new Date().toISOString().slice(0, 7);

function ChannelsPage() {
  const { t, i18n } = useTranslation();
  const { jobId } = useParams();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [view, setView] = useState(null); // null: the API picks; then 'real' or 'simulated'
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [sort, setSort] = useState(null);
  const [commentary, setCommentary] = useState(undefined); // undefined: not asked; null: none; list: shown
  const [asking, setAsking] = useState(false);
  const [cost, setCost] = useState({ channel: '', month: thisMonth(), amount: '' });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setCommentary(undefined);
    setData(await getChannels(companyId, jobId, view));
  }, [companyId, jobId, view]);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getChannels(companyId, jobId, view)
      .then((body) => {
        if (cancelled) return;
        setCommentary(undefined);
        setData(body);
      })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId, jobId, view]);

  const askCommentary = async () => {
    setAsking(true);
    setError('');
    try {
      const body = await getCommentary(companyId, jobId, data.simulated ? 'simulated' : 'real', i18n.language);
      setCommentary(body.observations?.length ? body.observations : null);
    } catch (err) {
      setError(err.message);
    } finally {
      setAsking(false);
    }
  };

  const submitCost = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await saveCost(companyId, Number(jobId), { channel: cost.channel.trim(), period_month: cost.month, amount_vnd: Number(cost.amount) });
      setCost({ ...cost, amount: '' });
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  const importCsv = async (event) => {
    const file = event.target.files[0];
    event.target.value = '';
    if (!file) return;
    setError('');
    try {
      await uploadCostsCsv(companyId, Number(jobId), file);
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const toggleSort = (key) => setSort((current) => ({ key, dir: current?.key === key && current.dir === 'desc' ? 'asc' : 'desc' }));
  const rows = data ? (sort ? sortRows(data.table.rows, sort.key, sort.dir) : data.table.rows) : [];

  return (
    <div className="space-y-6 p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">{t('insights.eyebrow')}</p>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-950">{t('insights.channels.title')}</h1>
          {data && <p className="mt-1 text-sm font-semibold text-slate-600">{data.job.title}</p>}
          <p className="mt-1 text-sm text-slate-600">{t('insights.channels.intro')}</p>
        </div>
        <Link to={`/jobs/${jobId}/reality-check`} className={secondaryButton}>{t('insights.channels.toReality')}</Link>
      </header>
      <ErrorAlert message={error} />
      {!data && !error && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
      {data && (
        <>
          {data.has_real && data.has_simulated && <DataToggle simulated={data.simulated} onChange={setView} />}
          {data.simulated && <SimulatedBanner />}

          {rows.length === 0 ? (
            <p className={`${cardClass} text-sm font-semibold text-slate-600`}>{t('insights.channels.empty')}</p>
          ) : (
            <section className={`${cardClass} overflow-x-auto`}>
              <table className="w-full text-left text-sm" data-testid="channel-table">
                <thead>
                  <tr className="border-b border-slate-200 text-xs font-bold uppercase tracking-[0.08em] text-slate-400">
                    {COLUMNS.map((column) => (
                      <th
                        key={column.key}
                        scope="col"
                        aria-sort={sort?.key === column.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                        className="py-2 pr-3"
                      >
                        <button type="button" onClick={() => toggleSort(column.key)} className="font-bold uppercase tracking-[0.08em] hover:text-slate-900">
                          {t(`insights.channels.col.${column.key}`)}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.channel} data-testid={`channel-${row.channel}`} className="border-b border-slate-100">
                      {COLUMNS.map((column) => (
                        <td key={column.key} className="py-3 pr-3 tabular-nums text-slate-800">
                          {column.key === 'channel' ? (
                            <>
                              <span className="font-semibold text-slate-950">{row.channel}</span>
                              {row.small_sample && <span className="mt-1 block text-xs font-semibold text-amber-700">{t('insights.channels.smallSample')}</span>}
                            </>
                          ) : (
                            column.format ? (column.format(row, t) ?? '—') : row[column.key]
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section className={`${cardClass} space-y-3`}>
            <div className="flex items-center gap-3">
              <h2 className="text-base font-extrabold text-slate-950">{t('insights.channels.commentaryTitle')}</h2>
              <button type="button" onClick={askCommentary} disabled={asking || rows.length === 0} className={primaryButton}>
                {asking ? t('common.loading') : t('insights.channels.askCommentary')}
              </button>
            </div>
            {commentary === undefined && <p className="text-sm text-slate-500">{t('insights.channels.commentaryHint')}</p>}
            {commentary === null && <p role="status" className="text-sm font-semibold text-slate-600">{t('insights.channels.noCommentary')}</p>}
            {Array.isArray(commentary) && (
              <ul data-testid="commentary" className="list-disc space-y-1 pl-5 text-sm text-slate-800">
                {commentary.map((line) => <li key={line}>{line}</li>)}
              </ul>
            )}
          </section>

          {!data.simulated && (
            <section className={`${cardClass} space-y-3`}>
              <h2 className="text-base font-extrabold text-slate-950">{t('insights.channels.costTitle')}</h2>
              <p className="text-sm text-slate-600">{t('insights.channels.costHint')}</p>
              <form onSubmit={submitCost} className="flex flex-wrap items-end gap-3">
                <label className="text-xs font-bold text-slate-500">
                  {t('insights.channels.costChannel')}
                  <input required value={cost.channel} onChange={(e) => setCost({ ...cost, channel: e.target.value })} list="channel-names" className={`${inputClass} mt-1 block`} />
                  <datalist id="channel-names">{data.table.rows.map((row) => <option key={row.channel} value={row.channel} />)}</datalist>
                </label>
                <label className="text-xs font-bold text-slate-500">
                  {t('insights.channels.costMonth')}
                  <input required type="month" value={cost.month} onChange={(e) => setCost({ ...cost, month: e.target.value })} className={`${inputClass} mt-1 block`} />
                </label>
                <label className="text-xs font-bold text-slate-500">
                  {t('insights.channels.costAmount')}
                  <input required type="number" min="0" step="1" value={cost.amount} onChange={(e) => setCost({ ...cost, amount: e.target.value })} className={`${inputClass} mt-1 block`} />
                </label>
                <button type="submit" disabled={saving} className={primaryButton}>{t('insights.channels.costSave')}</button>
              </form>
              <label className="block text-xs font-bold text-slate-500">
                {t('insights.channels.costCsv')}
                <input type="file" accept=".csv,text/csv" onChange={importCsv} className="mt-1 block text-sm font-normal" />
              </label>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default ChannelsPage;
