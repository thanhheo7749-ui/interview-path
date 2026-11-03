import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { recordProbation } from '../../lib/posthire.js';
import { ConfirmBar, ErrorAlert, secondaryButton } from '../KbFeedback.jsx';

const RESULTS = ['passed', 'extended', 'failed'];

// HR or the manager records how probation ended. A person records it; nothing here is predicted or scored by AI.
function ProbationControl({ companyId, appId, initial = null }) {
  const { t } = useTranslation();
  const [pending, setPending] = useState(null);
  const [recorded, setRecorded] = useState(initial);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const confirm = async () => {
    setBusy(true);
    setError('');
    try {
      const row = await recordProbation(companyId, appId, pending);
      setRecorded(row.result);
      setPending(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="probation-title" data-testid="probation-control" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <h3 id="probation-title" className="text-sm font-extrabold text-slate-950">{t('onboarding.probation.title')}</h3>
      <p className="text-xs text-slate-500">{t('onboarding.probation.hint')}</p>
      <ErrorAlert message={error} />
      <div className="flex flex-wrap gap-2">
        {RESULTS.map((result) => (
          <button key={result} type="button" disabled={busy} onClick={() => setPending(result)} className={secondaryButton}>
            {t(`onboarding.probation.options.${result}`)}
          </button>
        ))}
      </div>
      {pending && (
        <ConfirmBar
          message={t('onboarding.probation.confirm', { result: t(`onboarding.probation.options.${pending}`) })}
          confirmLabel={t('onboarding.probation.confirmButton')}
          busy={busy}
          onConfirm={confirm}
          onCancel={() => setPending(null)}
        />
      )}
      {recorded && (
        <p data-testid="probation-recorded" className="text-sm font-bold text-slate-900">
          {t('onboarding.probation.recorded', { result: t(`onboarding.probation.options.${recorded}`, { defaultValue: recorded }) })}
        </p>
      )}
    </section>
  );
}

export default ProbationControl;
