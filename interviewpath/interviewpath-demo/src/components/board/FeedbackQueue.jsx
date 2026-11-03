import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { approveFeedback } from '../../lib/posthire.js';
import { ErrorAlert, primaryButton, secondaryButton } from '../KbFeedback.jsx';

// Drafts waiting for HR on this job: an alias and a short preview each. Approving sends them to the candidates.
function FeedbackQueue({ companyId, drafts, onOpen, onChanged }) {
  const { t } = useTranslation();
  const [picked, setPicked] = useState([]);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const chosen = picked.filter((id) => drafts.some((draft) => draft.application_id === id));

  if (drafts.length === 0) return null;

  const toggle = (id) => {
    setConfirming(false);
    setPicked((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));
  };
  const approve = async () => {
    setBusy(true);
    setError('');
    try {
      await approveFeedback(companyId, chosen);
      setPicked([]);
      setConfirming(false);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="feedback-queue-title" data-testid="feedback-queue" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="feedback-queue-title" className="text-base font-extrabold text-slate-950">
          {t('posthire.queue.title', { count: drafts.length })}
        </h2>
        <button type="button" onClick={() => setPicked(chosen.length === drafts.length ? [] : drafts.map((d) => d.application_id))} className="text-xs font-bold text-blue-700 underline">
          {chosen.length === drafts.length ? t('posthire.queue.clear') : t('posthire.queue.selectAll')}
        </button>
      </div>
      <p className="text-xs text-slate-600">{t('posthire.queue.intro')}</p>
      <ErrorAlert message={error} />
      <ul className="space-y-2">
        {drafts.map((draft) => (
          <li key={draft.application_id} data-testid={`draft-${draft.alias}`} className="flex items-start gap-3 rounded-xl border border-slate-200 p-3">
            <input
              type="checkbox"
              checked={chosen.includes(draft.application_id)}
              onChange={() => toggle(draft.application_id)}
              aria-label={t('posthire.queue.select', { alias: draft.alias })}
              className="mt-1 h-4 w-4 rounded border-slate-300"
            />
            <div className="min-w-0 flex-1">
              <button type="button" onClick={() => onOpen(draft.application_id)} className="text-sm font-extrabold text-slate-950 underline">{draft.alias}</button>
              <p className="mt-1 line-clamp-2 text-xs text-slate-600">{draft.preview}</p>
            </div>
          </li>
        ))}
      </ul>
      {chosen.length > 0 && (confirming ? (
        <div role="alertdialog" aria-label={t('posthire.queue.confirmTitle')} className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-amber-900">{t('posthire.queue.confirm', { count: chosen.length })}</p>
          <div className="flex gap-2">
            <button type="button" disabled={busy} onClick={approve} className={primaryButton}>{t('posthire.queue.confirmButton', { count: chosen.length })}</button>
            <button type="button" onClick={() => setConfirming(false)} className={secondaryButton}>{t('common.cancel')}</button>
          </div>
        </div>
      ) : (
        <button type="button" onClick={() => setConfirming(true)} className={primaryButton}>{t('posthire.queue.approve', { count: chosen.length })}</button>
      ))}
    </section>
  );
}

export default FeedbackQueue;
