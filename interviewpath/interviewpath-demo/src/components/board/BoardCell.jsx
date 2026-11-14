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
        'flex h-full min-h-60 flex-col p-5',
        gem ? 'bg-violet-50/55 ring-2 ring-inset ring-violet-300/80' : 'bg-white',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
        <div>
          <h2 id={`cell-title-${cellKey}`} className="flex items-center gap-2 text-base font-extrabold tracking-tight text-slate-950">
            {gem && (
              <span className="inline-flex h-5 w-5 items-center justify-center rounded bg-violet-600 text-white" aria-hidden="true">
                <Gem size={13} />
              </span>
            )}
            {t(`board.cells.${cellKey}.title`)}
          </h2>
          <p className="mt-0.5 text-xs font-medium text-slate-500">{t(`board.cells.${cellKey}.axes`)}</p>
        </div>
        <span
          data-testid={`count-${cellKey}`}
          className={[
            'shrink-0 rounded-md px-2.5 py-1 text-xs font-bold tabular-nums',
            gem ? 'bg-violet-900 text-white' : undecided > 0 ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700',
          ].join(' ')}
          title={t('board.undecidedOf', { undecided, total: cards.length })}
        >
          {t('board.toDecide', { count: undecided })}
        </span>
      </div>

      {feedbackPending > 0 && (
        <p data-testid={`feedback-pending-${cellKey}`} className="mt-2 text-xs font-bold text-amber-800">
          {t('posthire.pending', { count: feedbackPending })}
        </p>
      )}
      <p className="mt-2 text-xs leading-relaxed text-slate-600">
        {gem && <strong className="mr-1.5 font-bold text-violet-900">{t('board.cells.hidden_gem.callout')}</strong>}
        {t(`board.cells.${cellKey}.hint`)}
      </p>

      {chosen.length > 0 && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
          {confirming ? (
            <div role="alertdialog" aria-label={t('board.bulk.confirmTitle')} className="space-y-2">
              <p className="font-bold text-red-900">{t('board.bulk.confirm', { count: chosen.length })}</p>
              <div className="flex gap-2">
                <button type="button" disabled={busy} onClick={reject} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-60">
                  {t('board.bulk.confirmButton', { count: chosen.length })}
                </button>
                <button type="button" onClick={() => setConfirming(false)} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-800">
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

      <div className="mt-3.5 space-y-2.5">
        {cards.length === 0 && <p className="py-6 text-center text-xs font-medium text-slate-400">{t('board.emptyCell')}</p>}
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
