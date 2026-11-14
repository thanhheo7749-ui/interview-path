import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CONSENT_WITHDRAWN, getCandidateAvatarUrl, getCandidateInitials, getCandidatePalette } from '../lib/board.js';

const CV_TONE = {
  meets: 'border border-emerald-200 bg-emerald-50 text-emerald-800',
  not_met: 'border border-amber-200 bg-amber-50 text-amber-900',
};
const DECISION_TONE = {
  approved: 'border border-emerald-300 bg-emerald-100 text-emerald-900',
  rejected: 'border border-rose-200 bg-rose-50 text-rose-800',
};

function CandidateCard({ card, selected, checked, onToggle, onClick }) {
  const { t } = useTranslation();
  const [imgErr, setImgErr] = useState(false);
  const decided = card.hr_decision !== 'pending';
  const [fg, bg] = getCandidatePalette(card.id);
  const initials = getCandidateInitials(card.candidate_name, card.alias);

  return (
    <article
      data-testid={`card-${card.alias}`}
      className={[
        'group relative rounded-xl border bg-white p-3.5 transition-colors',
        selected
          ? 'border-blue-600 bg-blue-50/25 shadow-sm ring-1 ring-blue-600'
          : 'border-slate-200/90 hover:border-slate-300 hover:bg-slate-50/40',
        decided ? 'opacity-75' : '',
      ].join(' ')}
    >
      <div className="flex items-start gap-3">
        {onToggle && (
          <input
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            aria-label={t('board.selectCard', { alias: card.alias })}
            className="mt-2 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-600"
          />
        )}
        <button type="button" onClick={onClick} className="flex min-w-0 flex-1 items-start gap-3 text-left">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200/90 text-xs font-extrabold"
            style={{ backgroundColor: bg, color: fg }}
          >
            {!imgErr ? (
              <img
                src={getCandidateAvatarUrl(card.candidate_name, card.alias, card.id)}
                alt={card.candidate_name || card.alias}
                className="h-full w-full object-cover"
                onError={() => setImgErr(true)}
              />
            ) : (
              <span>{initials}</span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-sm font-bold text-slate-950 group-hover:text-blue-700">
                {card.candidate_name || card.alias}
                {card.candidate_name && <span className="ml-1.5 text-xs font-normal text-slate-400">({card.alias})</span>}
              </p>
              {card.source_channel && (
                <span className="shrink-0 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-semibold text-slate-600">
                  {card.source_channel}
                </span>
              )}
            </div>
            {(card.candidate_email || card.candidate_phone) && (
              <p className="mt-0.5 truncate text-xs text-slate-500">
                {card.candidate_email}
                {card.candidate_email && card.candidate_phone ? ` · ${card.candidate_phone}` : card.candidate_phone}
              </p>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {card.cv_status && (
                <span className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${CV_TONE[card.cv_status] ?? 'bg-slate-100 text-slate-600'}`}>
                  {t(`board.cvStatus.${card.cv_status}`)}
                </span>
              )}
              {card.interview_band && (
                <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-700">
                  {t(`board.band.${card.interview_band}`)}
                </span>
              )}
              {card.fast_tracked && (
                <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-800">{t('board.fastTracked')}</span>
              )}
              {decided && (
                <span data-testid="decided-badge" className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${DECISION_TONE[card.hr_decision] ?? 'bg-slate-100 text-slate-600'}`}>
                  {t(`board.decision.${card.hr_decision}`, { defaultValue: card.hr_decision })}
                </span>
              )}
            </div>
            {card.analysis_status === 'not_taken' && (
              <p data-testid="interview-note" className="mt-1.5 text-xs font-medium text-amber-800">{t('board.notTaken')}</p>
            )}
            {card.analysis_status === CONSENT_WITHDRAWN && (
              <p data-testid="interview-note" className="mt-1.5 text-xs font-medium text-amber-800">{t('board.consentWithdrawn')}</p>
            )}
            {card.analysis_status === 'transcription_failed' && (
              <p data-testid="transcription-note" className="mt-1.5 text-xs font-medium text-amber-800">{t('board.lanes.transcription_failed')}</p>
            )}
            <p className="mt-1.5 text-[11px] font-medium text-slate-400">{t(`board.stage.${card.stage}`, { defaultValue: card.stage })}</p>
            {card.hidden_text_detected && <p className="mt-1 text-xs text-slate-500">{t('board.hiddenText')}</p>}
          </div>
        </button>
      </div>
    </article>
  );
}

export default CandidateCard;
