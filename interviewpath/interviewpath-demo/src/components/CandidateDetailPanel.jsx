import { X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getApplication } from '../lib/board.js';
import DecisionBar from './board/DecisionBar.jsx';
import EvidenceTable from './board/EvidenceTable.jsx';
import TranscriptPanel from './board/TranscriptPanel.jsx';
import { ErrorAlert } from './KbFeedback.jsx';

// Reads in the order HR should: the transcript first, then the evidence, then the AI suggestion.
function CandidateDetailPanel({ companyId, appId, onClose, onChanged }) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getApplication(companyId, appId)
      .then((data) => { if (!cancelled) setDetail(data); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId, appId]);

  const changed = useCallback(async () => {
    setDetail(await getApplication(companyId, appId));
    await onChanged();
  }, [companyId, appId, onChanged]);

  return (
    <aside
      role="complementary"
      aria-label={t('board.detail.title')}
      data-testid="detail-panel"
      className="fixed inset-y-0 right-0 z-40 w-full max-w-2xl overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-panel"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">{t('board.detail.title')}</p>
          <h2 className="text-xl font-extrabold text-slate-950">{detail?.alias ?? ''}</h2>
        </div>
        <button type="button" onClick={onClose} aria-label={t('board.detail.close')} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100">
          <X size={18} />
        </button>
      </div>
      <ErrorAlert message={error} />
      {!detail && !error && <p className="mt-4 text-sm text-slate-500">{t('common.loading')}</p>}
      {detail && (
        <div className="mt-4 space-y-6">
          <div className="flex flex-wrap gap-1.5 text-xs font-bold">
            {detail.cv_status && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{t(`board.cvStatus.${detail.cv_status}`)}</span>}
            {detail.interview_band && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{t(`board.band.${detail.interview_band}`)}</span>}
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{t(`board.stage.${detail.stage}`, { defaultValue: detail.stage })}</span>
            {detail.cv_status_corrected && <span className="rounded-full bg-blue-50 px-2.5 py-1 text-blue-700">{t('board.cvCorrection.corrected')}</span>}
          </div>
          {detail.hidden_text_detected && <p className="text-xs text-slate-500">{t('board.hiddenText')}</p>}
          {detail.fast_tracked && <p className="text-sm font-semibold text-slate-700">{t('board.fastTrackedNote')}</p>}
          {detail.analysis_status === 'failed' && <p className="text-sm font-semibold text-red-700">{t('board.analysisFailed')}</p>}
          {detail.cv_status_correction_reason && (
            <p className="text-xs text-slate-600">{t('board.cvCorrection.reasonShown', { reason: detail.cv_status_correction_reason })}</p>
          )}

          <TranscriptPanel companyId={companyId} appId={appId} turns={detail.transcript} />
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
        </div>
      )}
    </aside>
  );
}

export default CandidateDetailPanel;
