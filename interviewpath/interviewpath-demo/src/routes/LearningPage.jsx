import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';
import { ErrorAlert, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import { addResource, deleteResource, listResources, listSkills } from '../lib/posthire.js';

const EMPTY = { skill_node_id: '', title: '', url: '', provider: '', language: 'en' };

// Feedback links only to courses in this list, so no link a candidate sees was ever made up.
function LearningPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [rows, setRows] = useState(null);
  const [skills, setSkills] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => setRows(await listResources(companyId)), [companyId]);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    Promise.all([listResources(companyId), listSkills(companyId)])
      .then(([resources, nodes]) => {
        if (cancelled) return;
        setRows(resources);
        setSkills(nodes);
      })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId]);

  const change = (key) => (e) => setForm((current) => ({ ...current, [key]: e.target.value }));
  const run = async (action) => {
    setBusy(true);
    setError('');
    try {
      await action();
      await reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const submit = (e) => {
    e.preventDefault();
    run(async () => {
      await addResource(companyId, { ...form, skill_node_id: Number(form.skill_node_id) });
      setForm(EMPTY);
    });
  };

  return (
    <div className="space-y-6 p-8">
      <header>
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">{t('posthire.learning.eyebrow')}</p>
        <h1 className="text-2xl font-extrabold text-slate-950">{t('posthire.learning.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('posthire.learning.intro')}</p>
      </header>
      <ErrorAlert message={error} />

      <form onSubmit={submit} aria-label={t('posthire.learning.add')} className={`${cardClass} grid gap-3 md:grid-cols-2`}>
        <label className="text-xs font-bold text-slate-600">
          {t('posthire.learning.skill')}
          <select required value={form.skill_node_id} onChange={change('skill_node_id')} className={`${inputClass} mt-1 w-full`}>
            <option value="">{t('posthire.learning.chooseSkill')}</option>
            {skills.map((skill) => <option key={skill.id} value={skill.id}>{skill.title}</option>)}
          </select>
        </label>
        <label className="text-xs font-bold text-slate-600">
          {t('posthire.learning.name')}
          <input required value={form.title} onChange={change('title')} className={`${inputClass} mt-1 w-full`} />
        </label>
        <label className="text-xs font-bold text-slate-600">
          {t('posthire.learning.url')}
          <input required value={form.url} onChange={change('url')} placeholder="https://" className={`${inputClass} mt-1 w-full`} />
        </label>
        <label className="text-xs font-bold text-slate-600">
          {t('posthire.learning.provider')}
          <input value={form.provider} onChange={change('provider')} className={`${inputClass} mt-1 w-full`} />
        </label>
        <label className="text-xs font-bold text-slate-600">
          {t('posthire.learning.language')}
          <input value={form.language} onChange={change('language')} className={`${inputClass} mt-1 w-full`} />
        </label>
        <div className="flex items-end">
          <button type="submit" disabled={busy} className={primaryButton}>{t('posthire.learning.addButton')}</button>
        </div>
      </form>

      <section className={cardClass} aria-label={t('posthire.learning.listTitle')}>
        {!rows && !error && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
        {rows && rows.length === 0 && <p className="text-sm text-slate-500">{t('posthire.learning.empty')}</p>}
        {rows && rows.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs font-bold uppercase tracking-wider text-slate-500">
                <th className="py-2">{t('posthire.learning.skill')}</th>
                <th>{t('posthire.learning.name')}</th>
                <th>{t('posthire.learning.provider')}</th>
                <th>{t('posthire.learning.language')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} data-testid={`resource-${row.id}`} className="border-t border-slate-100">
                  <td className="py-2">{row.skill_title}</td>
                  <td><a href={row.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-blue-700 underline">{row.title}</a></td>
                  <td>{row.provider}</td>
                  <td>{row.language}</td>
                  <td className="text-right">
                    <button type="button" disabled={busy} onClick={() => run(() => deleteResource(companyId, row.id))} className={secondaryButton}>
                      {t('common.remove')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default LearningPage;
