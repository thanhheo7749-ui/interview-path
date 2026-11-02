import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  correctCvStatus, decide, fastTrack, grantRestart, retryAnalysis, revealIdentity,
} from '../../lib/board.js';
import { ErrorAlert, inputClass, primaryButton, secondaryButton } from '../KbFeedback.jsx';

// Every action here is a human choice. AI output never reaches these buttons.
function DecisionBar({ companyId, detail, onChanged }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState(null); // 'reveal' | 'cv' | 'reject' | null
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState(false);
  const [identity, setIdentity] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const appId = detail.id;
  const awaiting = detail.stage === 'ready_for_hr' && detail.hr_decision === 'pending';
  const failed = detail.stage === 'ready_for_hr' && detail.analysis_status === 'failed';
  const invited = detail.stage === 'invited';
  const otherLabel = detail.cv_status === 'meets' ? 'not_met' : 'meets';

  const run = async (action, after) => {
    setBusy(true);
    setError('');
    try {
      const result = await action();
      after?.(result);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const submitCorrection = () => {
    if (!reason.trim()) {
      setReasonError(true);
      return;
    }
    run(() => correctCvStatus(companyId, appId, otherLabel, reason.trim()), () => {
      setMode(null);
      setReason('');
    });
  };
  const openMode = (next) => {
    setMode(next);
    setReason('');
    setReasonError(false);
    setError('');
  };

  return (
    <section aria-labelledby="decision-title" data-testid="decision-bar" className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <h3 id="decision-title" className="text-sm font-extrabold text-slate-950">{t('board.actions.title')}</h3>
      <ErrorAlert message={error} />

      {detail.hr_decision !== 'pending' && (
        <p data-testid="decided-state" className="text-sm font-bold text-slate-900">
          {t(`board.decision.${detail.hr_decision}`, { defaultValue: detail.hr_decision })}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {awaiting && (
          <>
            <button type="button" disabled={busy} onClick={() => run(() => decide(companyId, appId, 'approved'))} className={primaryButton}>
              {t('board.actions.approve')}
            </button>
            <button type="button" disabled={busy} onClick={() => openMode('reject')} className={secondaryButton}>
              {t('board.actions.reject')}
            </button>
            {detail.cv_status && (
              <button type="button" disabled={busy} onClick={() => openMode('cv')} className={secondaryButton}>
                {t('board.actions.correctCv')}
              </button>
            )}
            {detail.restart_available && (
              <button type="button" disabled={busy} onClick={() => run(() => grantRestart(companyId, appId))} className={secondaryButton}>
                {t('board.actions.restart')}
              </button>
            )}
          </>
        )}
        {invited && (
          <button type="button" disabled={busy} onClick={() => run(() => fastTrack(companyId, appId))} className={secondaryButton}>
            {t('board.actions.fastTrack')}
          </button>
        )}
        {failed && (
          <button type="button" disabled={busy} onClick={() => run(() => retryAnalysis(companyId, appId))} className={secondaryButton}>
            {t('board.actions.retry')}
          </button>
        )}
        {!identity && (
          <button type="button" disabled={busy} onClick={() => openMode('reveal')} className={secondaryButton}>
            {t('board.actions.reveal')}
          </button>
        )}
      </div>

      {mode === 'reject' && (
        <div role="alertdialog" aria-label={t('board.actions.reject')} className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-amber-900">{t('board.actions.rejectConfirm')}</p>
          <div className="flex gap-2">
            <button type="button" disabled={busy} onClick={() => run(() => decide(companyId, appId, 'rejected'), () => setMode(null))} className={primaryButton}>
              {t('board.actions.rejectConfirmButton')}
            </button>
            <button type="button" onClick={() => setMode(null)} className={secondaryButton}>{t('common.cancel')}</button>
          </div>
        </div>
      )}

      {mode === 'reveal' && (
        <div role="alertdialog" aria-label={t('board.reveal.title')} className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-amber-900">{t('board.reveal.confirm')}</p>
          <div className="flex gap-2">
            <button type="button" disabled={busy} onClick={() => run(() => revealIdentity(companyId, appId), (who) => { setIdentity(who); setMode(null); })} className={primaryButton}>
              {t('board.reveal.confirmButton')}
            </button>
            <button type="button" onClick={() => setMode(null)} className={secondaryButton}>{t('common.cancel')}</button>
          </div>
        </div>
      )}

      {mode === 'cv' && (
        <div role="group" aria-label={t('board.cvCorrection.title')} className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
          <p className="text-sm font-semibold text-slate-800">
            {t('board.cvCorrection.change', { from: t(`board.cvStatus.${detail.cv_status}`), to: t(`board.cvStatus.${otherLabel}`) })}
          </p>
          <label className="block text-xs font-bold text-slate-600">
            {t('board.cvCorrection.reason')}
            <textarea
              value={reason}
              onChange={(e) => { setReason(e.target.value); setReasonError(false); }}
              rows={2}
              className={`${inputClass} mt-1 w-full`}
            />
          </label>
          {reasonError && <p role="alert" className="text-xs font-semibold text-red-700">{t('board.cvCorrection.required')}</p>}
          <div className="flex gap-2">
            <button type="button" disabled={busy} onClick={submitCorrection} className={primaryButton}>{t('board.cvCorrection.submit')}</button>
            <button type="button" onClick={() => setMode(null)} className={secondaryButton}>{t('common.cancel')}</button>
          </div>
        </div>
      )}

      {identity && (
        <p data-testid="revealed-identity" className="rounded-xl bg-white p-3 text-sm font-semibold text-slate-900">
          {identity.name} ({identity.email})
          <span className="mt-1 block text-xs font-normal text-slate-500">{t('board.reveal.logged')}</span>
        </p>
      )}
    </section>
  );
}

export default DecisionBar;
