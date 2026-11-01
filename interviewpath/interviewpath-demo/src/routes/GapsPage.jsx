import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';
import { EmptyState, ErrorAlert, cardClass, secondaryButton } from '../components/KbFeedback.jsx';
import { listGaps, resolveGap } from '../lib/kb.js';

function GapsPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [gaps, setGaps] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    listGaps(companyId)
      .then((data) => {
        if (!cancelled) setGaps(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const resolve = async (gap) => {
    setError('');
    try {
      await resolveGap(companyId, gap.group_id);
      setGaps((current) => current.filter((g) => g.group_id !== gap.group_id));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('gaps.title')}</h1>
      <p className="text-sm text-slate-600">{t('gaps.intro')}</p>
      <ErrorAlert message={error} />

      <h2 className="text-lg font-extrabold tracking-tight">{t('gaps.heading')}</h2>
      {gaps && gaps.length === 0 && <EmptyState>{t('gaps.empty')}</EmptyState>}
      {(gaps ?? []).map((gap) => (
        <section key={gap.group_id} className={`${cardClass} flex flex-wrap items-center justify-between gap-4`}>
          <div>
            <p className="font-bold text-slate-950">{gap.sample_question}</p>
            <p className="mt-1 text-sm text-slate-500">{t('gaps.count', { count: gap.count })}</p>
          </div>
          <button type="button" onClick={() => resolve(gap)} className={secondaryButton}>
            {t('gaps.resolve')}
          </button>
        </section>
      ))}
    </div>
  );
}

export default GapsPage;
