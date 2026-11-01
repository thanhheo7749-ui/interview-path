import { useTranslation } from 'react-i18next';

const CV_TONE = { meets: 'bg-emerald-50 text-emerald-700', not_met: 'bg-amber-50 text-amber-800' };

// The card carries an alias only. Names stay hidden until HR reveals them.
function CandidateCard({ card, selected, checked, onToggle, onClick }) {
  const { t } = useTranslation();
  const decided = card.hr_decision !== 'pending';

  return (
    <article
      data-testid={`card-${card.alias}`}
      className={[
        'rounded-2xl border bg-white p-4 shadow-card transition',
        selected ? 'border-blue-500 ring-2 ring-blue-200' : 'border-slate-200 hover:border-blue-200',
        decided ? 'opacity-70' : '',
      ].join(' ')}
    >
      <div className="flex items-start gap-3">
        {onToggle && (
          <input
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            aria-label={t('board.selectCard', { alias: card.alias })}
            className="mt-1 h-4 w-4 rounded border-slate-300"
          />
        )}
        <button type="button" onClick={onClick} className="min-w-0 flex-1 text-left">
          <p className="truncate text-sm font-extrabold text-slate-950">{card.alias}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {card.cv_status && (
              <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${CV_TONE[card.cv_status] ?? 'bg-slate-100 text-slate-600'}`}>
                {t(`board.cvStatus.${card.cv_status}`)}
              </span>
            )}
            {card.interview_band && (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">
                {t(`board.band.${card.interview_band}`)}
              </span>
            )}
            {card.fast_tracked && (
              <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700">{t('board.fastTracked')}</span>
            )}
            {decided && (
              <span data-testid="decided-badge" className="rounded-full bg-slate-950 px-2.5 py-1 text-xs font-bold text-white">
                {t(`board.decision.${card.hr_decision}`, { defaultValue: card.hr_decision })}
              </span>
            )}
          </div>
          <p className="mt-2 text-xs font-semibold text-slate-500">{t(`board.stage.${card.stage}`, { defaultValue: card.stage })}</p>
          {card.hidden_text_detected && <p className="mt-2 text-xs text-slate-500">{t('board.hiddenText')}</p>}
        </button>
      </div>
    </article>
  );
}

export default CandidateCard;
