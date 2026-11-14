import { Check, Copy, Download, ExternalLink, Eye, EyeOff, FileText, KeyRound, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CANDIDATE_PORTAL_URL,
  CONSENT_WITHDRAWN,
  downloadCvFile,
  getApplication,
  getCandidateAvatarUrl,
  getCandidateInitials,
  getCandidatePalette,
  inviteFromHold,
   updateContact,
} from '../lib/board.js';
import { BriefWorkflow } from './board/BriefEditor.jsx';
import DecisionBar from './board/DecisionBar.jsx';
import EvidenceTable from './board/EvidenceTable.jsx';
import OutcomeControl from './board/OutcomeControl.jsx';
import OnboardingStart from './board/OnboardingStart.jsx';
import FeedbackEditor from './board/FeedbackEditor.jsx';
import HrScorecard from './board/HrScorecard.jsx';
import TranscriptPanel from './board/TranscriptPanel.jsx';
import { ErrorAlert } from './KbFeedback.jsx';

// Reads in the order HR should: the candidate profile & CV first, then the transcript, then the evidence, then the AI suggestion.
function CandidateDetailPanel({ companyId, appId, onClose, onChanged }) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');
  const [deleted, setDeleted] = useState(false);
  const [contactEmail, setContactEmail] = useState('');
  const [contactName, setContactName] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [showFullCv, setShowFullCv] = useState(true);
  const [showPw, setShowPw] = useState(false);
  const [copiedField, setCopiedField] = useState('');
  const [imgErr, setImgErr] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setImgErr(false);
    getApplication(companyId, appId)
      .then((data) => { if (!cancelled) setDetail(data); })
      .catch((err) => {
        if (cancelled) return;
        // The board no longer lists a deleted application, so a stale card is the one way to reach this.
        if (err.status === 404) setDeleted(true);
        else setError(err.message);
      });
    return () => { cancelled = true; };
  }, [companyId, appId]);

  const changed = useCallback(async () => {
    setDetail(await getApplication(companyId, appId));
    await onChanged();
  }, [companyId, appId, onChanged]);

  const handleSaveContact = async (e) => {
    e.preventDefault();
    if (!contactEmail.trim()) return;
    setActionBusy(true);
    setError('');
    try {
      await updateContact(companyId, appId, { email: contactEmail.trim(), name: contactName.trim() || detail?.candidate_name || null });
      await changed();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionBusy(false);
    }
  };

  const handleInviteFromHold = async () => {
    setActionBusy(true);
    setError('');
    try {
      await inviteFromHold(companyId, appId);
      await changed();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionBusy(false);
    }
  };

  const handleDownloadCv = async () => {
    try {
      await downloadCvFile(companyId, appId, detail?.candidate_name || detail?.alias || 'CV');
    } catch (err) {
      setError(err.message);
    }
  };

  const [fg, bg] = getCandidatePalette(detail?.id || appId);
  const initials = getCandidateInitials(detail?.candidate_name, detail?.alias);

  return (
    <aside
      role="complementary"
      aria-label={t('board.detail.title')}
      data-testid="detail-panel"
      className="fixed inset-y-0 right-0 z-40 w-full max-w-2xl overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-panel"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3.5">
          <div
            className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-slate-200 text-base font-extrabold shadow-sm"
            style={{ backgroundColor: bg, color: fg }}
          >
            {detail && !imgErr ? (
              <img
                src={getCandidateAvatarUrl(detail.candidate_name, detail.alias, detail.id)}
                alt={detail.candidate_name || detail.alias}
                className="h-full w-full object-cover"
                onError={() => setImgErr(true)}
              />
            ) : (
              <span>{initials}</span>
            )}
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">{t('board.detail.title')}</p>
            <h2 className="text-xl font-extrabold text-slate-950">
              {detail?.candidate_name || detail?.alias || ''}
              {detail?.candidate_name && detail?.alias && (
                <span className="ml-2 text-sm font-semibold text-slate-400">({detail.alias})</span>
              )}
            </h2>
            {(detail?.candidate_email || detail?.candidate_phone || detail?.source_channel) && (
              <p className="mt-1 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-600">
                {detail.candidate_email && <span>{detail.candidate_email}</span>}
                {detail.candidate_phone && <span>• {detail.candidate_phone}</span>}
                {detail.source_channel && (
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-700">
                    {detail.source_channel}
                  </span>
                )}
              </p>
            )}
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label={t('board.detail.close')} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100">
          <X size={18} />
        </button>
      </div>
      <ErrorAlert message={error} />
      {!detail && !error && !deleted && <p className="mt-4 text-sm text-slate-500">{t('common.loading')}</p>}
      {(deleted || detail?.anonymized) && (
        <p role="status" data-testid="anonymized-notice" className="mt-4 rounded-xl bg-slate-100 p-4 text-sm font-semibold text-slate-700">
          {t('board.anonymizedNotice')}
        </p>
      )}
      {detail && !detail.anonymized && (
        <div className="mt-4 space-y-6">
          <div className="flex flex-wrap gap-1.5 text-xs font-bold">
            {detail.cv_status && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{t(`board.cvStatus.${detail.cv_status}`)}</span>}
            {detail.interview_band && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{t(`board.band.${detail.interview_band}`)}</span>}
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{t(`board.stage.${detail.stage}`, { defaultValue: detail.stage })}</span>
            {detail.cv_status_corrected && <span className="rounded-full bg-blue-50 px-2.5 py-1 text-blue-700">{t('board.cvCorrection.corrected')}</span>}
          </div>
          {detail.hidden_text_detected && <p className="text-xs text-slate-500">{t('board.hiddenText')}</p>}
          {detail.fast_tracked && <p className="text-sm font-semibold text-slate-700">{t('board.fastTrackedNote')}</p>}
          {detail.analysis_status === 'not_taken' && <p data-testid="interview-note" className="text-sm font-semibold text-amber-800">{t('board.notTaken')}</p>}
          {detail.analysis_status === CONSENT_WITHDRAWN && <p data-testid="interview-note" className="text-sm font-semibold text-amber-800">{t('board.consentWithdrawn')}</p>}
          {detail.long_pause && <p data-testid="long-pause-note" className="text-xs text-slate-500">{t('board.longPause')}</p>}
          {detail.analysis_status === 'failed' && <p className="text-sm font-semibold text-red-700">{t('board.analysisFailed')}</p>}
          {detail.analysis_status === 'transcription_failed' && <p data-testid="transcription-note" className="text-sm font-semibold text-amber-800">{t('board.transcriptionFailed')}</p>}
          {!detail.cv_status && detail.stage === 'cv_failed' && !detail.cv_consent_withdrawn && <p data-testid="cv-failed-note" className="text-sm font-semibold text-amber-800">{t('board.cvFailed')}</p>}
          {detail.cv_consent_withdrawn && detail.stage === 'cv_failed' && <p data-testid="cv-consent-note" className="text-sm font-semibold text-amber-800">{t('board.cvConsentWithdrawn')}</p>}
          {detail.cv_status_correction_reason && (
            <p className="text-xs text-slate-600">{t('board.cvCorrection.reasonShown', { reason: detail.cv_status_correction_reason })}</p>
          )}

          {detail.stage === 'missing_contact' && (
            <form onSubmit={handleSaveContact} className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-xs font-bold text-amber-900">
                {t('board.missingContactNote', { defaultValue: 'This CV has no extractable email. Fill in the candidate email to send the AI interview invite:' })}
              </p>
              <div className="flex flex-wrap gap-2">
                <input
                  type="text"
                  placeholder={detail.candidate_name || 'Candidate name'}
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  className="rounded-xl border border-amber-300 bg-white px-3 py-1.5 text-xs"
                />
                <input
                  type="email"
                  required
                  placeholder="candidate@example.com"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                  className="min-w-56 flex-1 rounded-xl border border-amber-300 bg-white px-3 py-1.5 text-xs"
                />
                <button
                  type="submit"
                  disabled={actionBusy}
                  className="rounded-xl bg-amber-800 px-3.5 py-1.5 text-xs font-bold text-white"
                >
                  {t('board.saveContact', { defaultValue: 'Save & Process CV' })}
                </button>
              </div>
            </form>
          )}

          {detail.stage === 'cv_hold' && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-xs font-semibold text-amber-900">
                {t('board.cvHoldNote', { defaultValue: 'Held: 0% of must-have requirements matched on CV. You can still invite this candidate manually.' })}
              </p>
              <button
                type="button"
                disabled={actionBusy}
                onClick={handleInviteFromHold}
                className="rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white"
              >
                {t('board.inviteFromHold', { defaultValue: 'Invite to AI interview anyway' })}
              </button>
            </div>
          )}

          {detail.account_created && detail.candidate_email && (
            <section className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600 text-white">
                    <KeyRound size={14} />
                  </div>
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-emerald-900">
                    {t('board.accountSectionTitle', { defaultValue: 'Auto-Provisioned Candidate Account (Round 1 AI Interview)' })}
                  </h3>
                </div>
                {detail.claim_token && (
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard?.writeText(`${CANDIDATE_PORTAL_URL}/claim/${detail.claim_token}`);
                        setCopiedField('magic');
                        setTimeout(() => setCopiedField(''), 2000);
                      }}
                      className="inline-flex items-center gap-1 rounded-lg bg-emerald-700 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-emerald-800"
                    >
                      {copiedField === 'magic' ? <Check size={12} /> : <Copy size={12} />}
                      {copiedField === 'magic'
                        ? t('board.copiedMagicLink', { defaultValue: 'Copied Magic Link!' })
                        : t('board.copyMagicLink', { defaultValue: 'Copy 1-Click Magic Link' })}
                    </button>
                    <a
                      href={`${CANDIDATE_PORTAL_URL}/claim/${detail.claim_token}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 rounded-lg border border-emerald-300 bg-white px-2.5 py-1 text-[11px] font-bold text-emerald-800 hover:bg-emerald-100"
                    >
                      <ExternalLink size={12} />
                      {t('board.openInterviewRoom', { defaultValue: 'Open Interview Room' })}
                    </a>
                  </div>
                )}
              </div>
              <div className="mt-2.5 flex flex-wrap items-center gap-4 text-xs text-slate-700">
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-slate-500">
                    {t('board.accountEmailLabel', { defaultValue: 'Account:' })}
                  </span>
                  <code className="rounded bg-white px-2 py-0.5 font-mono font-bold text-slate-900">
                    {detail.candidate_email}
                  </code>
                </div>
                {detail.default_password && (
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-slate-500">
                      {t('board.defaultPasswordLabel', { defaultValue: 'Default Password:' })}
                    </span>
                    <code className="rounded bg-white px-2 py-0.5 font-mono font-bold text-emerald-800">
                      {showPw ? detail.default_password : '••••••••••'}
                    </code>
                    <button
                      type="button"
                      onClick={() => setShowPw((v) => !v)}
                      className="rounded p-1 text-slate-500 hover:bg-white"
                    >
                      {showPw ? <EyeOff size={13} /> : <Eye size={13} />}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard?.writeText(detail.default_password);
                        setCopiedField('pw');
                        setTimeout(() => setCopiedField(''), 2000);
                      }}
                      className="rounded p-1 text-slate-500 hover:bg-white"
                    >
                      {copiedField === 'pw' ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
                    </button>
                  </div>
                )}
              </div>
            </section>
          )}

          {detail.cv_text_blind && (
            <section data-testid="candidate-cv-section" className="rounded-2xl border border-blue-200 bg-slate-50 p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
                    <FileText size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-extrabold text-slate-900">
                      {t('board.cvSectionTitle', { defaultValue: 'Candidate Resume (CV)' })}
                    </h3>
                    <p className="text-[11px] font-medium text-slate-500">
                      {detail.cv_suffix ? `Original format: ${detail.cv_suffix.toUpperCase()}` : 'CV Text'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowFullCv((v) => !v)}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-100"
                  >
                    {showFullCv ? <EyeOff size={14} /> : <Eye size={14} />}
                    {showFullCv
                      ? t('board.hideCv', { defaultValue: 'Collapse CV' })
                      : t('board.viewCv', { defaultValue: 'View Full CV' })}
                  </button>
                  {detail.has_cv_file && (
                    <button
                      type="button"
                      onClick={handleDownloadCv}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-700"
                    >
                      <Download size={14} />
                      {t('board.downloadCv', { defaultValue: 'Download Original CV' })}
                    </button>
                  )}
                </div>
              </div>
              {showFullCv && (
                <div className="mt-3 max-h-80 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 font-sans text-xs leading-relaxed whitespace-pre-wrap text-slate-800 shadow-inner">
                  {detail.cv_text_blind}
                </div>
              )}
            </section>
          )}

          <TranscriptPanel companyId={companyId} appId={appId} turns={detail.transcript} masked={detail.identity_masked} />
          <EvidenceTable
            companyId={companyId}
            appId={appId}
            requirements={detail.requirements}
            claims={detail.claims}
            cultureNotes={detail.culture_notes}
            turns={detail.transcript}
          />

          <section aria-labelledby="suggestion-title" data-testid="ai-suggestion" className="rounded-2xl border border-violet-200 bg-violet-50 p-4">
            <h3 id="suggestion-title" className="text-sm font-extrabold text-violet-900">{t('board.suggestion.title')}</h3>
            <p className="mt-1 text-sm text-slate-800">{detail.suggestion ? detail.suggestion.text : t('board.suggestion.none')}</p>
          </section>

          <DecisionBar key={appId} companyId={companyId} detail={detail} onChanged={changed} />

          {detail.hr_decision === 'rejected' && <FeedbackEditor key={`feedback-${appId}`} companyId={companyId} appId={appId} onChanged={onChanged} />}

          {detail.hr_decision === 'approved' && (
            <>
              <BriefWorkflow
                key={`brief-${appId}`}
                companyId={companyId}
                appId={appId}
                audioPositions={new Set(detail.transcript.filter((turn) => turn.has_audio).map((turn) => turn.position))}
              />
              <HrScorecard key={`scorecard-${appId}`} companyId={companyId} appId={appId} />
              <OutcomeControl key={`outcome-${appId}`} companyId={companyId} appId={appId} initial={detail.final_outcome} onRecorded={changed} />
              {detail.final_outcome === 'hired' && <OnboardingStart key={`onboarding-${appId}`} companyId={companyId} appId={appId} planId={detail.onboarding_plan_id} />}
            </>
          )}
        </div>
      )}
    </aside>
  );
}

export default CandidateDetailPanel;
