import { Gem } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { isBulkSelectable, isUndecided } from '../../lib/board.js';
import CandidateCard from '../CandidateCard.jsx';

// `onBulkReject(ids)` resolves when the rejection is done. The count is confirmed before it runs.
function BoardCell({ cellKey, cards, selectedId, onSelect, onBulkReject, feedbackPending = 0 }) {
  const { t } = useTranslation();
  const [picked, setPicked] = useState([]);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const gem = cellKey === 'hidden_gem';
  const undecided = cards.filter(isUndecided).length;
  const chosen = picked.filter((id) => cards.some((card) => card.id === id && isBulkSelectable(card)));

  const toggle = (id) => {
    setConfirming(false);
    setPicked((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));
  };
  const reject = async () => {
    setBusy(true);
    try {
      await onBulkReject(chosen);
      setPicked([]);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  return (
    <section
      data-testid={`cell-${cellKey}`}
      aria-labelledby={`cell-title-${cellKey}`}
      className={[
        'flex min-h-56 flex-col rounded-2xl border bg-white p-5 shadow-card',
        gem ? 'border-2 border-violet-300 bg-violet-50/40' : 'border-slate-200',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id={`cell-title-${cellKey}`} className="flex items-center gap-2 text-base font-extrabold text-slate-950">
            {gem && <Gem size={17} className="text-violet-600" aria-hidden="true" />}
            {t(`board.cells.${cellKey}.title`)}
          </h2>
          <p className="mt-1 text-xs font-semibold text-slate-500">{t(`board.cells.${cellKey}.axes`)}</p>
        </div>
        <span
          data-testid={`count-${cellKey}`}
          className="shrink-0 rounded-full bg-slate-950 px-2.5 py-1 text-xs font-bold text-white"
          title={t('board.undecidedOf', { undecided, total: cards.length })}
        >
          {t('board.toDecide', { count: undecided })}
        </span>
      </div>
      {feedbackPending > 0 && (
        <p data-testid={`feedback-pending-${cellKey}`} className="mt-2 text-xs font-bold text-amber-800">{t('posthire.pending', { count: feedbackPending })}</p>
      )}
      {gem && <p className="mt-2 text-sm font-bold text-violet-800">{t('board.cells.hidden_gem.callout')}</p>}
      <p className="mt-2 text-sm text-slate-600">{t(`board.cells.${cellKey}.hint`)}</p>

      {chosen.length > 0 && (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm">
          {confirming ? (
            <div role="alertdialog" aria-label={t('board.bulk.confirmTitle')} className="space-y-2">
              <p className="font-bold text-red-900">{t('board.bulk.confirm', { count: chosen.length })}</p>
              <div className="flex gap-2">
                <button type="button" disabled={busy} onClick={reject} className="rounded-xl bg-red-600 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-60">
                  {t('board.bulk.confirmButton', { count: chosen.length })}
                </button>
                <button type="button" onClick={() => setConfirming(false)} className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-800">
                  {t('common.cancel')}
                </button>
              </div>
            </div>
          ) : (
            <button type="button" onClick={() => setConfirming(true)} className="text-xs font-bold text-red-800 underline">
              {t('board.bulk.button', { count: chosen.length })}
            </button>
          )}
        </div>
      )}

      <div className="mt-4 space-y-3">
        {cards.length === 0 && <p className="text-sm font-semibold text-slate-400">{t('board.emptyCell')}</p>}
        {cards.map((card) => (
          <CandidateCard
            key={card.id}
            card={card}
            selected={card.id === selectedId}
            checked={chosen.includes(card.id)}
            onToggle={isBulkSelectable(card) ? () => toggle(card.id) : null}
            onClick={() => onSelect(card.id)}
          />
        ))}
      </div>
    </section>
  );
}

export default BoardCell;
