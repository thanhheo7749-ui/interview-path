import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import BoardCell from '../components/board/BoardCell.jsx';
import CandidateCard from '../components/CandidateCard.jsx';
import CandidateDetailPanel from '../components/CandidateDetailPanel.jsx';
import { ErrorAlert } from '../components/KbFeedback.jsx';
import { LANES, bulkReject, getBoard } from '../lib/board.js';

function BoardPage() {
  const { t } = useTranslation();
  const { jobId } = useParams();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [board, setBoard] = useState(null);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);

  const reload = useCallback(async () => {
    setBoard(await getBoard(companyId, jobId));
  }, [companyId, jobId]);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getBoard(companyId, jobId)
      .then((data) => { if (!cancelled) setBoard(data); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId, jobId]);

  const rejectMany = async (ids) => {
    setError('');
    try {
      await bulkReject(companyId, jobId, ids);
      await reload();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-8 p-8">
      <header>
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">{t('board.eyebrow')}</p>
        <h1 className="text-2xl font-extrabold text-slate-950">{board?.job?.title ?? t('board.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('board.intro')}</p>
      </header>
      <ErrorAlert message={error} />
      {!board && !error && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
      {board && (
        <>
          <div className="grid grid-cols-[auto_1fr_1fr] gap-x-4 gap-y-2">
            <span />
            <p className="text-center text-xs font-bold uppercase tracking-wider text-slate-500">{t('board.axes.much')}</p>
            <p className="text-center text-xs font-bold uppercase tracking-wider text-slate-500">{t('board.axes.little')}</p>
            <p className="self-center text-xs font-bold uppercase tracking-wider text-slate-500 [writing-mode:vertical-rl] rotate-180">{t('board.axes.meets')}</p>
            <BoardCell cellKey="priority" cards={board.cells.priority} selectedId={selectedId} onSelect={setSelectedId} onBulkReject={rejectMany} />
            <BoardCell cellKey="strong_cv_unclear" cards={board.cells.strong_cv_unclear} selectedId={selectedId} onSelect={setSelectedId} onBulkReject={rejectMany} />
            <p className="self-center text-xs font-bold uppercase tracking-wider text-slate-500 [writing-mode:vertical-rl] rotate-180">{t('board.axes.notMet')}</p>
            <BoardCell cellKey="hidden_gem" cards={board.cells.hidden_gem} selectedId={selectedId} onSelect={setSelectedId} onBulkReject={rejectMany} />
            <BoardCell cellKey="not_enough_evidence" cards={board.cells.not_enough_evidence} selectedId={selectedId} onSelect={setSelectedId} onBulkReject={rejectMany} />
          </div>

          <section aria-label={t('board.lanes.title')} className="space-y-3">
            <h2 className="text-base font-extrabold text-slate-950">{t('board.lanes.title')}</h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {LANES.map((lane) => (
                <div key={lane} data-testid={`lane-${lane}`} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-extrabold text-slate-950">{t(`board.lanes.${lane}`)}</h3>
                    <span data-testid={`count-${lane}`} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
                      {board.lanes[lane]?.length ?? 0}
                    </span>
                  </div>
                  <div className="mt-3 space-y-3">
                    {(board.lanes[lane] ?? []).map((card) => (
                      <CandidateCard key={card.id} card={card} selected={card.id === selectedId} onClick={() => setSelectedId(card.id)} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {selectedId != null && (
        <CandidateDetailPanel key={selectedId} companyId={companyId} appId={selectedId} onClose={() => setSelectedId(null)} onChanged={reload} />
      )}
    </div>
  );
}

export default BoardPage;
