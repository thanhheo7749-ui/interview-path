import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { createOnboarding } from '../../lib/posthire.js';
import { ErrorAlert, primaryButton, secondaryButton } from '../KbFeedback.jsx';

// For a hire: open the 30-60-90 plan, or ask for a draft. Drafting calls the AI, so it waits for the click.
function OnboardingStart({ companyId, appId, planId = null }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const create = async () => {
    setBusy(true);
    setError('');
    try {
      const plan = await createOnboarding(companyId, appId);
      navigate(`/onboarding/${plan.id}`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="onboarding-start-title" data-testid="onboarding-start" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <h3 id="onboarding-start-title" className="text-sm font-extrabold text-slate-950">{t('onboarding.start.title')}</h3>
      <ErrorAlert message={error} />
      {planId ? (
        <Link to={`/onboarding/${planId}`} className={`${secondaryButton} inline-block`}>{t('onboarding.start.open')}</Link>
      ) : (
        <>
          <p className="text-xs text-slate-500">{t('onboarding.start.hint')}</p>
          <button type="button" disabled={busy} onClick={create} className={primaryButton}>
            {busy ? t('onboarding.start.creating') : t('onboarding.start.create')}
          </button>
        </>
      )}
    </section>
  );
}

export default OnboardingStart;
