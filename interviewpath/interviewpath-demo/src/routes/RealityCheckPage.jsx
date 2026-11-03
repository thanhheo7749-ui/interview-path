import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import { ErrorAlert, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import { DataToggle, SimulatedBanner } from '../components/SimulatedBanner.jsx';
import { getChannels, getRealityCheck, percent, saveThresholds } from '../lib/insights.js';

const TONES = {
  not_enough_data: 'bg-slate-100 text-slate-700',
  consider_nice_to_have: 'bg-amber-100 text-amber-900',
  review: 'bg-blue-100 text-blue-900',
  keep: 'bg-emerald-100 text-emerald-900',
};

function RealityCheckPage() {
  const { t } = useTranslation();
  const { jobId } = useParams();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [flags, setFlags] = useState(null); // which kinds of data the job has, from the channel view
  const [view, setView] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getChannels(companyId, jobId)
      .then((body) => {
        if (cancelled) return;
        setFlags({ has_real: body.has_real, has_simulated: body.has_simulated, title: body.job.title });
        setView(body.simulated ? 'simulated' : 'real');
      })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId, jobId]);

  useEffect(() => {
    if (companyId == null || view == null) return undefined;
    let cancelled = false;
    getRealityCheck(companyId, jobId, view)
      .then((body) => {
        if (cancelled) return;
        setReport(body);
        setForm((current) => current ?? { low_pct: body.thresholds.low_pct, high_pct: body.thresholds.high_pct, min_hired: body.thresholds.min_hired });
      })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId, jobId, view]);

  const submitThresholds = async (event) => {
    event.preventDefault();
    setSaving(true);
    setSaved(false);
    setError('');
    try {
      await saveThresholds(companyId, { reality_low_pct: Number(form.low_pct), reality_high_pct: Number(form.high_pct), reality_min_hired: Number(form.min_hired) });
      setReport(await getRealityCheck(companyId, jobId, view));
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const field = (key, label) => (
    <label className="text-xs font-bold text-slate-500">
      {label}
      <input required type="number" min={key === 'min_hired' ? 1 : 0} max={key === 'min_hired' ? undefined : 100} step="1" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={`${inputClass} mt-1 block w-28`} />
    </label>
  );

  // The editor when the job has no JD Studio draft. Nothing is applied from here either way.
  const studioLink = report?.draft_id ? `/jd-studio/${report.draft_id}` : `/jobs/${jobId}`;

  return (
    <div className="space-y-6 p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">{t('insights.eyebrow')}</p>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-950">{t('insights.reality.title')}</h1>
          {flags && <p className="mt-1 text-sm font-semibold text-slate-600">{flags.title}</p>}
          <p className="mt-1 text-sm text-slate-600">{t('insights.reality.intro')}</p>
        </div>
        <Link to={`/jobs/${jobId}/channels`} className={secondaryButton}>{t('insights.reality.toChannels')}</Link>
      </header>
      <ErrorAlert message={error} />
      {!report && !error && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
      {report && flags && (
        <>
          {flags.has_real && flags.has_simulated && <DataToggle simulated={report.simulated} onChange={setView} />}
          {report.simulated && <SimulatedBanner />}
          <p className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">{t('insights.reality.probationNote')}</p>

          {report.rows.length === 0 ? (
            <p className={`${cardClass} text-sm font-semibold text-slate-600`}>{t('insights.reality.empty')}</p>
          ) : (
            <ul className="space-y-3">
              {report.rows.map((row) => (
                <li key={row.requirement_id} data-testid={`requirement-${row.requirement_id}`} className={`${cardClass} space-y-3`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <h2 className="text-base font-extrabold text-slate-950">{row.text}</h2>
                    <span className={`rounded-full px-3 py-1 text-xs font-bold ${TONES[row.suggestion]}`}>{t(`insights.reality.suggestion.${row.suggestion}`)}</span>
                  </div>
                  {row.suggestion === 'not_enough_data' ? (
                    <p className="text-sm text-slate-600">{t('insights.reality.notEnough', { hired: row.hired_total, min: report.thresholds.min_hired })}</p>
                  ) : (
                    <p className="text-sm text-slate-700">{t('insights.reality.heldBy', { with: row.hired_with_requirement, hired: row.hired_total })}</p>
                  )}
                  <dl className="grid grid-cols-1 gap-2 text-sm md:grid-cols-3">
                    <div><dt className="text-xs font-bold text-slate-500">{t('insights.reality.cvMiss')}</dt><dd className="font-semibold tabular-nums">{percent(row.cv_miss_rate) ?? '—'}</dd></div>
                    <div><dt className="text-xs font-bold text-slate-500">{t('insights.reality.corrections')}</dt><dd className="font-semibold tabular-nums">{row.hr_label_corrections}</dd></div>
                    <div><dt className="text-xs font-bold text-slate-500">{t('insights.reality.probationPassed')}</dt><dd className="font-semibold tabular-nums">{row.probation_passed_without_requirement}</dd></div>
                  </dl>
                  {row.too_strict_signal && <p className="text-sm font-semibold text-amber-800">{t('insights.reality.tooStrict')}</p>}
                  {row.action && (
                    <Link to={studioLink} className="inline-block text-sm font-bold text-blue-600 underline-offset-2 hover:underline">
                      {report.draft_id ? t('insights.reality.openStudio') : t('insights.reality.openEditor')}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}

          {form && (
            <section className={`${cardClass} space-y-3`}>
              <h2 className="text-base font-extrabold text-slate-950">{t('insights.reality.thresholdsTitle')}</h2>
              <p className="text-sm text-slate-600">{t('insights.reality.thresholdsHint')}</p>
              <form onSubmit={submitThresholds} className="flex flex-wrap items-end gap-3">
                {field('low_pct', t('insights.reality.low'))}
                {field('high_pct', t('insights.reality.high'))}
                {field('min_hired', t('insights.reality.minHired'))}
                <button type="submit" disabled={saving} className={primaryButton}>{t('common.save')}</button>
                {saved && <span role="status" className="text-sm font-semibold text-emerald-700">{t('insights.reality.saved')}</span>}
              </form>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default RealityCheckPage;
