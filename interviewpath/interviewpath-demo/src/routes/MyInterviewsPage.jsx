import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import { EmptyState, ErrorAlert, cardClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import { listMyInterviews } from '../lib/bridges.js';

// The manager's interviews: briefs HR approved and sent. The list shows the candidate's alias only.
function MyInterviewsPage() {
  const { t, i18n } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    listMyInterviews(companyId)
      .then((data) => { if (!cancelled) setItems(data); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId]);

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('bridges.interviews.title')}</h1>
      <ErrorAlert message={error} />
      {items && items.length === 0 && <EmptyState>{t('bridges.interviews.empty')}</EmptyState>}
      {items && items.length > 0 && (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.application_id} data-testid={`interview-${item.application_id}`} className={`${cardClass} flex items-center justify-between gap-4`}>
              <div>
                <p className="font-bold">{item.job_title}</p>
                <p className="text-sm text-slate-600">
                  {item.alias}
                  {item.sent_at && ` · ${t('bridges.interviews.sentOn', { date: new Date(item.sent_at).toLocaleDateString(i18n.language) })}`}
                </p>
                <p data-testid="scored-state" className="text-xs font-semibold text-slate-500">
                  {item.scored ? t('bridges.interviews.scored') : t('bridges.interviews.notScored')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {item.onboarding_plan_id && (
                  <Link to={`/onboarding/${item.onboarding_plan_id}`} className={secondaryButton}>
                    {t('onboarding.start.open')}
                  </Link>
                )}
                <Link to={`/my-interviews/${item.application_id}`} className={primaryButton}>
                  {t('bridges.interviews.open')}
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default MyInterviewsPage;
