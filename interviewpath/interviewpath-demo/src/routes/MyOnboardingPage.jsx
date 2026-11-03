import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import { EmptyState, ErrorAlert, cardClass, secondaryButton } from '../components/KbFeedback.jsx';
import { getMyOnboarding, tickOnboardingItem } from '../lib/posthire.js';

const PHASES = [30, 60, 90];

// The hire's own checklist. Ticking an item stores the time it was ticked and nothing else about use.
function MyOnboardingPage() {
  const { t, i18n } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [plans, setPlans] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getMyOnboarding(companyId)
      .then((data) => { if (!cancelled) setPlans(data); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId]);

  const tick = async (itemId) => {
    setError('');
    try {
      const done = await tickOnboardingItem(companyId, itemId);
      setPlans((previous) => previous.map((plan) => ({
        ...plan, items: plan.items.map((item) => (item.id === itemId ? { ...item, done_at: done.done_at } : item)),
      })));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('onboarding.mine.title')}</h1>
      <p className="text-sm text-slate-600">{t('onboarding.mine.privacy')}</p>
      <ErrorAlert message={error} />
      {plans && plans.length === 0 && <EmptyState>{t('onboarding.mine.empty')}</EmptyState>}
      {plans?.map((plan) => (
        <div key={plan.id} className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            {PHASES.map((days) => (
              <section key={days} data-testid={`phase-${days}`} aria-label={t('onboarding.plan.phase', { days })} className={`${cardClass} space-y-3`}>
                <h2 className="text-sm font-extrabold">{t('onboarding.plan.phase', { days })}</h2>
                <ul className="space-y-3">
                  {plan.items.filter((item) => item.phase === days).map((item) => (
                    <li key={item.id} data-testid="my-item" className="space-y-1 rounded-xl border border-slate-200 p-3">
                      <label className="flex items-start gap-2 text-sm font-semibold">
                        <input type="checkbox" checked={Boolean(item.done_at)} disabled={Boolean(item.done_at)} onChange={() => tick(item.id)} className="mt-1" />
                        <span>{item.title}</span>
                      </label>
                      {item.done_at && (
                        <p className="text-xs text-slate-500">{t('onboarding.mine.doneOn', { date: new Date(item.done_at).toLocaleDateString(i18n.language) })}</p>
                      )}
                      <p className="text-xs text-slate-500">
                        {item.learning_resource
                          ? <a href={item.learning_resource.url} target="_blank" rel="noopener noreferrer" className="underline">{item.learning_resource.title}</a>
                          : item.source_title}
                      </p>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <Link to="/copilot" className={`${secondaryButton} inline-block`}>{t('onboarding.mine.askCopilot')}</Link>
        </div>
      ))}
    </div>
  );
}

export default MyOnboardingPage;
