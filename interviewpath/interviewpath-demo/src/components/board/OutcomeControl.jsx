import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { recordOutcome } from '../../lib/bridges.js';
import { ConfirmBar, ErrorAlert, secondaryButton } from '../KbFeedback.jsx';

const OUTCOMES = ['hired', 'not_hired', 'offer_declined'];

// HR records what happened after the interviews. Each choice is asked about first; nothing here is set by AI.
function OutcomeControl({ companyId, appId, initial = null }) {
  const { t } = useTranslation();
  const [pending, setPending] = useState(null);
  const [recorded, setRecorded] = useState(initial);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const confirm = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await recordOutcome(companyId, appId, pending);
      setRecorded(result.final_outcome);
      setPending(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="outcome-title" data-testid="outcome-control" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <h3 id="outcome-title" className="text-sm font-extrabold text-slate-950">{t('bridges.outcome.title')}</h3>
      <p className="text-xs text-slate-500">{t('bridges.outcome.hint')}</p>
      <ErrorAlert message={error} />
      <div className="flex flex-wrap gap-2">
        {OUTCOMES.map((outcome) => (
          <button key={outcome} type="button" disabled={busy} onClick={() => setPending(outcome)} className={secondaryButton}>
            {t(`bridges.outcome.options.${outcome}`)}
          </button>
        ))}
      </div>
      {pending && (
        <ConfirmBar
          message={t('bridges.outcome.confirm', { outcome: t(`bridges.outcome.options.${pending}`) })}
          confirmLabel={t('bridges.outcome.confirmButton')}
          busy={busy}
          onConfirm={confirm}
          onCancel={() => setPending(null)}
        />
      )}
      {recorded && (
        <p data-testid="outcome-recorded" className="text-sm font-bold text-slate-900">
          {t('bridges.outcome.recorded', { outcome: t(`bridges.outcome.options.${recorded}`, { defaultValue: recorded }) })}
        </p>
      )}
    </section>
  );
}

export default OutcomeControl;
